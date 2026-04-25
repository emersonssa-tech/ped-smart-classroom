"""
Reconhecedor de intents.

Protocol: qualquer classe com o método `recognize(text) -> IntentResult`
satisfaz o contrato. Hoje temos só RuleBasedIntentRecognizer (regex).
Amanhã pode ter um NlpIntentRecognizer / LlmIntentRecognizer com o mesmo
Protocol — sem mudanças no service.
"""
import re
import string
import unicodedata
from dataclasses import dataclass, field
from typing import Protocol, Optional

from .intents import INTENTS, IntentRule


@dataclass(frozen=True)
class IntentResult:
    intent: Optional[str]                          # None quando nada bate
    confidence: float                           # 0-1 (hoje sempre 0 ou 1 com regras)
    entities: dict[str, str] = field(default_factory=dict)
    normalized_text: str = ""
    matched_pattern: Optional[str] = None          # regex que bateu (debug)


# ---------------------------------------------------------------------------
# Normalização — roda antes de qualquer match
# ---------------------------------------------------------------------------

_PUNCT_TABLE = str.maketrans("", "", string.punctuation + "¿¡—–…")


def _strip_accents(s: str) -> str:
    # NFD decompõe vogal+acento em dois codepoints, Mn = marca não-espaçada
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def normalize(text: str) -> str:
    """
    Pipeline: trim → lowercase → strip accents → strip punctuation → collapse spaces.

    Exemplo:
        "Próximo slide, por favor!"  →  "proximo slide por favor"
    """
    t = text.strip().lower()
    t = _strip_accents(t)
    t = t.translate(_PUNCT_TABLE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class IntentRecognizer(Protocol):
    def recognize(self, text: str) -> IntentResult: ...


# ---------------------------------------------------------------------------
# Implementação baseada em regras
# ---------------------------------------------------------------------------

class RuleBasedIntentRecognizer:
    """
    Varre INTENTS em ordem. A primeira regra cujo regex bate no texto
    normalizado ganha. Named groups do regex viram entities.
    """

    def __init__(self, rules: tuple[IntentRule, ...] = INTENTS) -> None:
        self._rules = rules

    def recognize(self, text: str) -> IntentResult:
        normalized = normalize(text)
        if not normalized:
            return IntentResult(intent=None, confidence=0.0, normalized_text="")

        for rule in self._rules:
            for pattern in rule.patterns:
                match = pattern.search(normalized)
                if match:
                    entities = {
                        k: v for k, v in match.groupdict().items() if v is not None
                    }
                    return IntentResult(
                        intent=rule.name,
                        confidence=1.0,
                        entities=entities,
                        normalized_text=normalized,
                        matched_pattern=pattern.pattern,
                    )

        return IntentResult(intent=None, confidence=0.0, normalized_text=normalized)


# Singleton compartilhado — trocar aqui é a única edição necessária
# para plugar NLP/LLM no futuro.
recognizer: IntentRecognizer = RuleBasedIntentRecognizer()


# ---------------------------------------------------------------------------
# API pública pedida pela spec: interpret_command(text) -> {intent, entities}
# ---------------------------------------------------------------------------

def interpret_command(text: str) -> dict:
    """
    Função utilitária solicitada na spec.
    Retorna dict {intent, entities} — delega para o recognizer singleton.
    """
    result = recognizer.recognize(text)
    return {"intent": result.intent, "entities": result.entities}
