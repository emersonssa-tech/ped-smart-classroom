from .handlers import register_subscribers
from .intents import INTENTS, INTENT_BY_NAME, IntentRule
from .recognizer import IntentRecognizer, IntentResult, interpret_command, normalize, recognizer
from .router import router

__all__ = [
    "router",
    "register_subscribers",
    # Introspecção pública
    "interpret_command",
    "normalize",
    "IntentResult",
    "IntentRecognizer",
    "IntentRule",
    "INTENTS",
    "INTENT_BY_NAME",
    "recognizer",
]
