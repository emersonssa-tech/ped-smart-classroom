"""
Telemetry recorder.

Subscriber que escuta os eventos de voz (publicados tanto por voice_engine
quanto por voice_ai) e grava entradas estruturadas na TelemetryStore.

A função classify_agreement() é o coração analítico — categoriza como
LLM e regras concordaram (ou não) usando o payload `shadow_rules` que o
voice_ai inclui quando rodou em modo LLM.
"""
import logging
from typing import Any, Optional

from ..core import Event, EventNames, event_bus
from .store import TelemetryStore, utcnow_iso

logger = logging.getLogger(__name__)


# Todos os eventos voice_* — recorder se inscreve em todos
_VOICE_EVENT_NAMES: tuple[str, ...] = (
    EventNames.VOICE_START_CLASS,
    EventNames.VOICE_NEXT_SLIDE,
    EventNames.VOICE_PREVIOUS_SLIDE,
    EventNames.VOICE_OPEN_ACTIVITY,
    EventNames.VOICE_PLAY_VIDEO,
    EventNames.VOICE_PAUSE_VIDEO,
    EventNames.VOICE_MARK_ATTENDANCE,
    EventNames.VOICE_TURN_ON_PROJECTOR,
    EventNames.VOICE_TURN_OFF_PROJECTOR,
    EventNames.VOICE_QUERY_CURRENT_CLASS,
    EventNames.VOICE_UNRECOGNIZED,
)


def classify_agreement(
    main_intent: Optional[str],
    main_entities: dict,
    rules_intent: Optional[str],
    rules_entities: dict,
) -> str:
    """
    Categoriza concordância entre o resultado principal (LLM) e o shadow (regras).

    - match              : mesmo intent + mesmas entities
    - match_intent_only  : mesmo intent, entities diferentes
    - rules_subset       : LLM extraiu mais entities que regras (super-set)
    - disagree           : intents diferentes, ambos não-null
    - llm_only           : regras=None, LLM=algo (LLM resolveu o que regras não pegavam)
    - rules_only         : LLM=None, regras=algo (regressão — LLM perdeu o que regras pegariam)
    - both_unrecognized  : nenhum reconheceu
    """
    if main_intent is None and rules_intent is None:
        return "both_unrecognized"
    if main_intent is None and rules_intent is not None:
        return "rules_only"
    if main_intent is not None and rules_intent is None:
        return "llm_only"
    if main_intent != rules_intent:
        return "disagree"

    # mesmos intents — comparar entities
    main_e = dict(main_entities or {})
    rules_e = dict(rules_entities or {})
    if main_e == rules_e:
        return "match"
    # se LLM "tem tudo" que regras tem, plus mais → super-set
    if all(rules_e.get(k) == v for k, v in rules_e.items() if k in main_e) \
            and set(rules_e.keys()).issubset(set(main_e.keys())):
        return "rules_subset"
    return "match_intent_only"


class TelemetryRecorder:
    def __init__(self, store: TelemetryStore) -> None:
        self._store = store

    async def on_voice_event(self, event: Event) -> None:
        p: dict[str, Any] = event.payload
        intent = p.get("intent")
        entities = p.get("entities") or {}
        source = p.get("source") or ("rules" if event.name != EventNames.VOICE_UNRECOGNIZED else "rules")
        mode = p.get("mode") or ("online" if source == "llm" else "offline")
        latency_ms = p.get("latency_ms")  # voice_ai inclui; voice_engine pode não incluir
        warning = p.get("warning")

        # Shadow (vem do voice_ai quando source=llm)
        shadow_rules = p.get("shadow_rules")  # {"intent": ..., "entities": {...}} ou None
        shadow_block = None
        if shadow_rules:
            agreement = classify_agreement(
                intent, entities,
                shadow_rules.get("intent"),
                shadow_rules.get("entities") or {},
            )
            shadow_block = {
                "rules_intent": shadow_rules.get("intent"),
                "rules_entities": shadow_rules.get("entities") or {},
                "agreement": agreement,
            }

        record = {
            "ts": utcnow_iso(),
            "event_name": event.name,
            "correlation_id": p.get("correlation_id"),
            "intent": intent,
            "entities": entities,
            "confidence": p.get("confidence"),
            "transcript": p.get("normalized_text") or p.get("raw_text"),
            "source": source,
            "mode": mode,
            "latency_ms": latency_ms,
            "warning": warning,
            "classroom_id": p.get("classroom_id"),
            "shadow": shadow_block,
        }
        await self._store.record(record)


def register_subscribers(store: TelemetryStore) -> None:
    rec = TelemetryRecorder(store)
    for name in _VOICE_EVENT_NAMES:
        event_bus.subscribe(name, rec.on_voice_event)
    logger.info(f"[Telemetry] inscrito em {len(_VOICE_EVENT_NAMES)} eventos voice_*")
