"""
Reserva de nomes de eventos do módulo companion.

Não publica nada ainda — só fixa a nomenclatura pra que quando o módulo
for implementado o resto do sistema (analytics, telemetry, memory) possa
se inscrever nesses eventos sem renomeação posterior.

Padrão snake_case, igual ao resto do EventNames.
"""


class CompanionEventNames:
    # Tablet ↔ servidor
    COMPANION_CONNECTED = "companion_connected"
    COMPANION_DISCONNECTED = "companion_disconnected"
    COMPANION_HEARTBEAT = "companion_heartbeat"

    # Periférico físico (Arduino/ESP) → servidor
    COMPANION_BUTTON_PRESSED = "companion_button_pressed"
    COMPANION_RFID_SCANNED = "companion_rfid_scanned"
    COMPANION_QUIZ_ANSWERED = "companion_quiz_answered"

    # Servidor → tablet (broadcasts derivados; opcional, ver DESIGN.md §3.2)
    COMPANION_CONTENT_PUSHED = "companion_content_pushed"
