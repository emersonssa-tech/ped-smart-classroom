"""
Subscribers de voice_engine — hoje todos stubs.

Cada handler loga o que seria feito quando o intent correspondente for ouvido
na sala. Quando chegar a hora de plugar hardware/API real (projetor, slide
deck, sistema de chamada, etc), é aqui que a ação concreta vai entrar — sem
mudar o resto do sistema.

Mantendo os stubs registrados desde já, garantimos que toda cadeia
intent → evento → subscriber está conectada e observável nos logs.
"""
import logging

from ..core import Event, EventNames, event_bus

logger = logging.getLogger(__name__)


# Cada handler é trivial hoje. Mantidos separados para que implementações
# reais evoluam independentes umas das outras.

async def on_start_class(event: Event) -> None:
    p = event.payload
    logger.info(f"[Voice/handler] start_class cid={p['correlation_id'][:8]} (seria: inicia fluxo de aula)")


async def on_next_slide(event: Event) -> None:
    p = event.payload
    logger.info(f"[Voice/handler] next_slide cid={p['correlation_id'][:8]} (seria: envia comando próximo slide)")


async def on_previous_slide(event: Event) -> None:
    p = event.payload
    logger.info(f"[Voice/handler] previous_slide cid={p['correlation_id'][:8]} (seria: envia comando slide anterior)")


async def on_open_activity(event: Event) -> None:
    p = event.payload
    activity_id = p["entities"].get("activity_id", "?")
    logger.info(f"[Voice/handler] open_activity id={activity_id} cid={p['correlation_id'][:8]}")


async def on_play_video(event: Event) -> None:
    p = event.payload
    logger.info(f"[Voice/handler] play_video cid={p['correlation_id'][:8]}")


async def on_pause_video(event: Event) -> None:
    p = event.payload
    logger.info(f"[Voice/handler] pause_video cid={p['correlation_id'][:8]}")


async def on_mark_attendance(event: Event) -> None:
    p = event.payload
    logger.info(f"[Voice/handler] mark_attendance cid={p['correlation_id'][:8]} (seria: abre chamada)")


async def on_turn_on_projector(event: Event) -> None:
    p = event.payload
    logger.info(f"[Voice/handler] turn_on_projector cid={p['correlation_id'][:8]} (seria: GPIO/HDMI-CEC ON)")


async def on_turn_off_projector(event: Event) -> None:
    p = event.payload
    logger.info(f"[Voice/handler] turn_off_projector cid={p['correlation_id'][:8]} (seria: GPIO/HDMI-CEC OFF)")


async def on_query_current_class(event: Event) -> None:
    # Só o voice_ai publica este evento (regras não reconhecem).
    # Num handler real: chamaria get_current_class na NuvemPed e falaria
    # ou mostraria na tela: "Você está dando Matemática para a 9A agora".
    p = event.payload
    logger.info(
        f"[Voice/handler] query_current_class cid={p['correlation_id'][:8]} "
        f"source={p.get('source')} (seria: TTS + consulta NuvemPed)"
    )


async def on_unrecognized(event: Event) -> None:
    p = event.payload
    logger.info(
        f"[Voice/handler] unrecognized cid={p['correlation_id'][:8]} "
        f"normalized={p['normalized_text']!r} (telemetria: registrar pra melhorar regras)"
    )


_BINDINGS = {
    EventNames.VOICE_START_CLASS:         on_start_class,
    EventNames.VOICE_NEXT_SLIDE:          on_next_slide,
    EventNames.VOICE_PREVIOUS_SLIDE:      on_previous_slide,
    EventNames.VOICE_OPEN_ACTIVITY:       on_open_activity,
    EventNames.VOICE_PLAY_VIDEO:          on_play_video,
    EventNames.VOICE_PAUSE_VIDEO:         on_pause_video,
    EventNames.VOICE_MARK_ATTENDANCE:     on_mark_attendance,
    EventNames.VOICE_TURN_ON_PROJECTOR:   on_turn_on_projector,
    EventNames.VOICE_TURN_OFF_PROJECTOR:  on_turn_off_projector,
    EventNames.VOICE_QUERY_CURRENT_CLASS: on_query_current_class,
    EventNames.VOICE_UNRECOGNIZED:        on_unrecognized,
}


def register_subscribers() -> None:
    for event_name, handler in _BINDINGS.items():
        event_bus.subscribe(event_name, handler)
