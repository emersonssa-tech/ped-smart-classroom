"""
Catálogo de eventos do sistema.

Event names são strings constantes — evita typos silenciosos entre quem
publica e quem se inscreve.

Os payloads são documentados como dicts tipados (TypedDict) para servir
de referência. Não há validação em runtime — confiamos nos publishers.
"""
from typing import TypedDict, Optional


class EventNames:
    TEACHER_DETECTED = "teacher_detected"
    CLASS_STARTED = "class_started"
    CLASS_ENDED = "class_ended"
    CONTENT_LOADED = "content_loaded"

    # Voice — um evento por intent (subscribers se inscrevem só no que interessa)
    VOICE_START_CLASS = "voice_start_class"
    VOICE_NEXT_SLIDE = "voice_next_slide"
    VOICE_PREVIOUS_SLIDE = "voice_previous_slide"
    VOICE_OPEN_ACTIVITY = "voice_open_activity"
    VOICE_PLAY_VIDEO = "voice_play_video"
    VOICE_PAUSE_VIDEO = "voice_pause_video"
    VOICE_MARK_ATTENDANCE = "voice_mark_attendance"
    VOICE_TURN_ON_PROJECTOR = "voice_turn_on_projector"
    VOICE_TURN_OFF_PROJECTOR = "voice_turn_off_projector"
    VOICE_QUERY_CURRENT_CLASS = "voice_query_current_class"  # novo — só voice_ai reconhece
    VOICE_UNRECOGNIZED = "voice_unrecognized"


# --- Payload shapes (documentação) ---

class TeacherDetectedPayload(TypedDict):
    correlation_id: str
    teacher_id: str
    teacher_name: str
    classroom_id: Optional[str]
    reference_time: str   # ISO datetime


class HorarioPayload(TypedDict):
    slot_id: str
    inicio: str   # "HH:MM"
    fim: str


class ClassStartedPayload(TypedDict):
    correlation_id: str
    teacher_id: str
    teacher_name: str
    turma: str
    disciplina: str
    horario: HorarioPayload
    reference_time: str


class ClassEndedPayload(TypedDict):
    correlation_id: str             # mesmo do class_started — pareia início↔fim
    teacher_id: Optional[str]
    classroom_id: Optional[str]
    ended_at: str                   # ISO datetime
    reason: str                     # "manual" | "timeout" | etc


class ContentLoadedPayload(TypedDict):
    correlation_id: str
    turma: str
    disciplina: str
    conteudo: str


class VoiceIntentPayload(TypedDict):
    """Payload publicado para cada intent de voz reconhecido (ou voice_unrecognized)."""
    correlation_id: str
    intent: Optional[str]          # None quando voice_unrecognized
    entities: dict[str, str]
    confidence: float
    raw_text: str               # texto original como veio
    normalized_text: str        # após normalização
    classroom_id: Optional[str]
    received_at: str            # ISO datetime
