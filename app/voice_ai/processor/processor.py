"""
Voice AI Processor — orquestra STT → LLM → parser → fallback → publish.

Função pública: process_voice_command(audio_input) -> VoiceCommandAIResponse.

Fluxo em modo 'online':
    audio → stt.transcribe()
          → llm.complete(system_prompt, transcript)
          → parse_llm_json(response)
          → validate (intent no catálogo? JSON OK?)
          → se válido: publica evento e retorna (source=llm)
          → se inválido OU falhou: cai em offline

Fluxo em modo 'offline':
    audio → stt.transcribe()
          → RuleBasedIntentRecognizer.recognize(transcript)
          → publica evento (ou voice_unrecognized)
          → retorna (source=rules)

Integração com event_bus: publica os MESMOS eventos que voice_engine publica
(voice_next_slide, etc). Os handlers existentes em voice_engine/handlers.py
reagem sem saber se veio de regex ou LLM.
"""
import json
import logging
import re
import time
import uuid
from datetime import datetime
from typing import Any, Optional

from ...core import Event, EventNames, event_bus
from ...voice_engine.recognizer import RuleBasedIntentRecognizer
from ..llm import LLMClient, LLMError
from ..prompts import SYSTEM_PROMPT, VALID_INTENTS, build_system_prompt, build_user_message
from ..schemas import VoiceCommandAIRequest, VoiceCommandAIResponse
from ..stt import STTClient

logger = logging.getLogger(__name__)


# Mapa intent → EventName.
# Reusa o catálogo do voice_engine pros 9 intents originais +
# o novo query_current_class (exclusivo do LLM).
INTENT_TO_EVENT: dict[str, str] = {
    "start_class":          EventNames.VOICE_START_CLASS,
    "next_slide":           EventNames.VOICE_NEXT_SLIDE,
    "previous_slide":       EventNames.VOICE_PREVIOUS_SLIDE,
    "open_activity":        EventNames.VOICE_OPEN_ACTIVITY,
    "play_video":           EventNames.VOICE_PLAY_VIDEO,
    "pause_video":          EventNames.VOICE_PAUSE_VIDEO,
    "mark_attendance":      EventNames.VOICE_MARK_ATTENDANCE,
    "turn_on_projector":    EventNames.VOICE_TURN_ON_PROJECTOR,
    "turn_off_projector":   EventNames.VOICE_TURN_OFF_PROJECTOR,
    "query_current_class":  EventNames.VOICE_QUERY_CURRENT_CLASS,
}


# --- Parser de JSON tolerante -----------------------------------------------

_JSON_OBJ_RE = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)


def parse_llm_json(raw: str) -> Optional[dict[str, Any]]:
    """
    Tenta 3 estratégias:
      1. raw é JSON válido
      2. JSON envolto em ```...```
      3. primeiro objeto {...} encontrado na string
    Retorna None se nenhuma funcionar.
    """
    if not raw:
        return None
    s = raw.strip()

    # 1) JSON puro
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # 2) Code block
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", s, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    # 3) Primeiro objeto válido em qualquer lugar do texto
    for m in _JSON_OBJ_RE.finditer(s):
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            continue

    return None


def validate_intent_json(parsed: Optional[dict[str, Any]]) -> Optional[tuple]:
    """
    Valida a forma do dict. Retorna (intent, entities, confidence) ou None se inválido.
    intent=None é VÁLIDO (significa "não reconhecido").
    """
    if not isinstance(parsed, dict):
        return None
    intent = parsed.get("intent")
    entities = parsed.get("entities", {})
    confidence = parsed.get("confidence", 0.0)

    if intent is not None:
        if not isinstance(intent, str) or intent not in VALID_INTENTS:
            return None
    if not isinstance(entities, dict):
        entities = {}
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    # garante strings nas entities (downstream espera str)
    entities = {str(k): str(v) for k, v in entities.items()}

    return intent, entities, confidence


# --- Processor --------------------------------------------------------------

class VoiceAIProcessor:
    def __init__(
        self,
        stt: STTClient,
        llm: Optional[LLMClient],
        mode: str = "auto",               # "auto" | "online" | "offline"
        max_tokens: int = 200,
        temperature: float = 0.0,
        json_mode: bool = True,
        shadow_rules_enabled: bool = True,
        memory_lookup_enabled: bool = True,
    ) -> None:
        self._stt = stt
        self._llm = llm
        self._mode = mode
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._json_mode = json_mode
        self._shadow_rules_enabled = shadow_rules_enabled
        self._memory_lookup = memory_lookup_enabled
        self._rules = RuleBasedIntentRecognizer()

    async def aclose(self) -> None:
        await self._stt.aclose()
        if self._llm is not None:
            await self._llm.aclose()

    # ---------- helpers de memory ----------

    def _memory_correction(self, transcript: str) -> Optional[dict]:
        """Busca correção exata no MemoryStore. Retorna None se não houver."""
        try:
            from ...memory import get_memory_store
            return get_memory_store().find_correction(transcript)
        except Exception:
            return None  # memory não inicializada (ex: testes isolados)

    def _memory_extension(self, transcript: str) -> str:
        """Constrói o bloco de exemplos pro prompt. Retorna string vazia se nada relevante."""
        try:
            from ...memory import get_memory_store, build_extension_block
            examples = get_memory_store().similar_examples(transcript, max_examples=5)
            return build_extension_block(examples)
        except Exception:
            return ""

    # ---------- API pública ----------

    async def process_voice_command(
        self, payload: VoiceCommandAIRequest
    ) -> VoiceCommandAIResponse:
        t0 = time.perf_counter()
        now = datetime.utcnow()
        correlation_id = str(uuid.uuid4())

        # 1) STT
        transcript = await self._stt.transcribe(payload.audio_input)

        # 2) decide modo efetivo
        mode = (payload.force_mode or self._mode).lower()
        effective_online = (mode == "online") or (mode == "auto" and self._llm is not None)

        # 3) tenta LLM; se falhar/inválido cai pras regras
        result_intent: Optional[str] = None
        result_entities: dict = {}
        result_confidence: float = 0.0
        source: str = "rules"
        warning: Optional[str] = None

        # 3a) MEMORY HOOK: correção exata como override (em qualquer modo, mas
        #     mais útil em offline onde não há LLM pra "aprender" via prompt).
        #     Se houver correção exata pra esse transcript, aplicamos diretamente.
        memory_override = self._memory_correction(transcript) if self._memory_lookup else None
        if memory_override and not effective_online:
            result_intent = memory_override["correct_intent"]
            result_entities = {}
            result_confidence = 1.0
            source = "memory"

        if effective_online and self._llm is not None and source == "rules":
            try:
                # 3b) MEMORY HOOK: monta extension do prompt com exemplos relevantes
                extension = self._memory_extension(transcript) if self._memory_lookup else ""
                system_prompt = build_system_prompt(extension)

                raw = await self._llm.complete(
                    system_prompt,
                    build_user_message(transcript),
                    max_tokens=self._max_tokens,
                    temperature=self._temperature,
                    json_mode=self._json_mode,
                )
                logger.debug(f"[VoiceAI] raw LLM response: {raw[:200]}")
                parsed = parse_llm_json(raw)
                validated = validate_intent_json(parsed)
                if validated is None:
                    warning = "LLM devolveu JSON/intent inválido — caindo em regras."
                    logger.warning(f"[VoiceAI] {warning} raw={raw[:200]!r}")
                else:
                    result_intent, result_entities, result_confidence = validated
                    source = "llm"
            except LLMError as exc:
                warning = f"LLM falhou ({type(exc).__name__}) — caindo em regras."
                logger.warning(f"[VoiceAI] {warning} detail={exc}")

        # 4) fallback pras regras, se necessário
        if source == "rules":
            rule_result = self._rules.recognize(transcript)
            result_intent = rule_result.intent
            result_entities = dict(rule_result.entities)
            result_confidence = rule_result.confidence
            shadow_rules = None  # já estamos usando regras como principal
        elif source == "memory":
            # source=memory já foi resolvido — não há shadow pra computar
            shadow_rules = None
        else:
            # source == "llm": shadow mode — roda regras em paralelo pra
            # alimentar telemetria comparativa (custo ~0ms, regex local)
            if self._shadow_rules_enabled:
                shadow = self._rules.recognize(transcript)
                shadow_rules = {
                    "intent": shadow.intent,
                    "entities": dict(shadow.entities),
                    "confidence": shadow.confidence,
                }
            else:
                shadow_rules = None

        # 5) mapeia intent → event
        if result_intent and result_intent in INTENT_TO_EVENT:
            event_name = INTENT_TO_EVENT[result_intent]
        else:
            event_name = EventNames.VOICE_UNRECOGNIZED
            result_intent = None

        latency_ms = int((time.perf_counter() - t0) * 1000)
        mode = "online" if effective_online else "offline"

        # 6) publica no event bus (mesmos eventos do voice_engine)
        await event_bus.publish(Event(
            name=event_name,
            payload={
                "correlation_id": correlation_id,
                "intent": result_intent,
                "entities": result_entities,
                "confidence": result_confidence,
                "raw_text": payload.audio_input,
                "normalized_text": transcript,
                "classroom_id": payload.classroom_id,
                "teacher_id": payload.teacher_id,
                "received_at": now.isoformat(),
                "source": source,           # "llm" | "rules"
                "mode": mode,               # "online" | "offline"
                "latency_ms": latency_ms,
                "warning": warning,
                "shadow_rules": shadow_rules,  # presente quando source=="llm" e shadow ativado
            },
        ))

        logger.info(
            f"[VoiceAI] cid={correlation_id[:8]} mode={mode} "
            f"source={source} intent={result_intent} conf={result_confidence:.2f} lat={latency_ms}ms"
        )

        return VoiceCommandAIResponse(
            recognized=result_intent is not None,
            intent=result_intent,
            entities=result_entities,
            confidence=result_confidence,
            transcript=transcript,
            source=source,
            mode="online" if effective_online else "offline",
            event_name=event_name,
            correlation_id=correlation_id,
            latency_ms=latency_ms,
            received_at=now,
            warning=warning,
        )
