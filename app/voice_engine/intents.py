"""
Catálogo declarativo de intents de voz.

Cada IntentRule é:
  - name: identificador do intent (ex: "next_slide")
  - event_name: evento que será publicado quando o intent for reconhecido
  - patterns: lista de regex. Primeira que bate → intent reconhecido.
              Regex usa texto JÁ normalizado (lowercase, sem acento, sem pontuação).
              Named groups `(?P<nome>...)` viram entities automaticamente.
  - examples: frases de exemplo (documentação + smoke test).

Ordem importa: regras mais específicas antes das mais genéricas.
Para adicionar um novo intent: acrescentar uma IntentRule em INTENTS.
Nada mais muda.
"""
import re
from dataclasses import dataclass, field

from ..core import EventNames


@dataclass(frozen=True)
class IntentRule:
    name: str
    event_name: str
    patterns: tuple[re.Pattern, ...]
    examples: tuple[str, ...] = field(default_factory=tuple)
    description: str = ""


# Regex são escritos em TEXTO NORMALIZADO — sem acento, minúsculo, sem pontuação.
# Ver recognizer.normalize().

INTENTS: tuple[IntentRule, ...] = (
    # ---- projetor (específico, antes de outros comandos de ligar/desligar) ----
    IntentRule(
        name="turn_on_projector",
        event_name=EventNames.VOICE_TURN_ON_PROJECTOR,
        patterns=(
            re.compile(r"\b(ligar?|liga|ligue|acender?|acende|acenda|inicializar?)\s+(o\s+)?projetor\b"),
        ),
        examples=("ligar projetor", "liga o projetor", "acenda o projetor"),
    ),
    IntentRule(
        name="turn_off_projector",
        event_name=EventNames.VOICE_TURN_OFF_PROJECTOR,
        patterns=(
            re.compile(r"\b(desligar?|desliga|desligue|apagar?|apaga|apague|encerrar?)\s+(o\s+)?projetor\b"),
        ),
        examples=("desligar projetor", "desliga o projetor", "apaga projetor"),
    ),

    # ---- slide ----
    IntentRule(
        name="next_slide",
        event_name=EventNames.VOICE_NEXT_SLIDE,
        patterns=(
            re.compile(r"\b(proxim[oa]|avancar?|avanca|avance)\s+(o\s+|a\s+)?(slide|pagina|lamina|tela)\b"),
            re.compile(r"\b(slide|pagina)\s+(proxim[oa]|seguinte)\b"),
            re.compile(r"^avanca(r|e)?$"),
        ),
        examples=("próximo slide", "avança o slide", "avançar página", "slide seguinte"),
    ),
    IntentRule(
        name="previous_slide",
        event_name=EventNames.VOICE_PREVIOUS_SLIDE,
        patterns=(
            re.compile(r"\b(slide|pagina|lamina|tela)\s+anterior\b"),
            re.compile(r"\banterior\b"),
            re.compile(r"\b(voltar?|volta|volte)\s+(o\s+|a\s+)?(slide|pagina|lamina|tela)\b"),
        ),
        examples=("slide anterior", "volta o slide", "anterior", "voltar página"),
    ),

    # ---- vídeo ----
    IntentRule(
        name="pause_video",
        event_name=EventNames.VOICE_PAUSE_VIDEO,
        patterns=(
            re.compile(r"\b(pausar?|pausa|pause|parar?|para|pare)\s+(o\s+)?(video|filme|reproducao)\b"),
            re.compile(r"\bpausa(r)?\b"),
        ),
        examples=("pausa o vídeo", "pausar vídeo", "para o vídeo"),
    ),
    IntentRule(
        name="play_video",
        event_name=EventNames.VOICE_PLAY_VIDEO,
        patterns=(
            re.compile(r"\b(tocar?|toca|toque|reproduz\w*|dar?\s+play|play)\s+(o\s+|no\s+|do\s+)?(video|filme)\b"),
            re.compile(r"\b(iniciar?|inicia|comecar?|comeca)\s+(o\s+)?video\b"),
        ),
        examples=("tocar o vídeo", "play no vídeo", "reproduz vídeo", "inicia o vídeo"),
    ),

    # ---- atividade ----
    IntentRule(
        name="open_activity",
        event_name=EventNames.VOICE_OPEN_ACTIVITY,
        patterns=(
            # com número: "abrir atividade 3"
            re.compile(r"\b(abrir?|abre|abra|mostrar?|mostra|exibir?|exiba)\s+(a\s+)?atividade\s+(?P<activity_id>\d+)\b"),
            # genérico sem número: "abrir atividade"
            re.compile(r"\b(abrir?|abre|abra|mostrar?|mostra|exibir?|exiba)\s+(a\s+)?atividade\b"),
            re.compile(r"\b(vai|va|ir)\s+(pra|para|a|ao|na)\s+atividade\s+(?P<activity_id>\d+)\b"),
        ),
        examples=("abrir atividade", "abrir atividade 3", "mostra a atividade 5", "vai pra atividade 2"),
    ),

    # ---- chamada / presença ----
    IntentRule(
        name="mark_attendance",
        event_name=EventNames.VOICE_MARK_ATTENDANCE,
        patterns=(
            re.compile(r"\b(marcar?|marca|registrar?|registra|fazer?|faz|faca)\s+(a\s+)?(presenca|chamada|frequencia)\b"),
            re.compile(r"\bchamada\b"),
        ),
        examples=("fazer chamada", "marcar presença", "registrar frequência", "chamada"),
    ),

    # ---- aula ----
    IntentRule(
        name="start_class",
        event_name=EventNames.VOICE_START_CLASS,
        patterns=(
            re.compile(r"\b(iniciar?|inicia|inicie|comecar?|comeca|comece)\s+(a\s+)?aula\b"),
            re.compile(r"\bvamos\s+comecar\b"),
            re.compile(r"\baula\s+iniciada\b"),
        ),
        examples=("iniciar aula", "começar a aula", "vamos começar", "comece a aula"),
    ),
)


# Atalho: name -> rule, usado para testes e introspecção
INTENT_BY_NAME: dict[str, IntentRule] = {r.name: r for r in INTENTS}
