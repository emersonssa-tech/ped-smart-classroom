"""
Portas (interfaces) do companion.

A escolha do transport (WebSocket vs MQTT vs SSE) e do driver físico
(ESP HTTP vs Arduino Serial) é independente do resto do sistema, contanto
que satisfaça estes Protocols. O módulo `services/` (futuro) vai depender
APENAS destas abstrações.
"""
from typing import Protocol, Optional

from .models import ContentPacket, Peripheral


class CompanionTransport(Protocol):
    """
    Canal servidor ↔ tablet.

    Implementações futuras possíveis:
      - WebSocketTransport       (FastAPI WS, 1 conexão por tablet)
      - MQTTTransport            (broker externo; melhor pra escala)
      - SSETransport             (server-sent events, só servidor → cliente)
      - PollingTransport         (fallback simples)

    Decidir conforme DESIGN.md §2.2.
    """

    async def push(self, packet: ContentPacket) -> None:
        """Envia conteúdo pro tablet. None target_device_id = broadcast da sala."""
        ...

    async def list_connected(self, classroom_id: Optional[str] = None) -> list[str]:
        """Retorna device_ids ativos (filtra por sala se passado)."""
        ...

    async def disconnect(self, device_id: str) -> None: ...

    async def aclose(self) -> None: ...


class ArduinoBridge(Protocol):
    """
    Bridge entre periféricos físicos e o event_bus.

    Implementações futuras possíveis:
      - HTTPArduinoBridge      (ESP faz POST /companion/peripheral/event)
      - MQTTArduinoBridge      (subscribe em ped/+/peripheral/+)
      - SerialArduinoBridge    (Arduino UNO via /dev/ttyUSB0; trava no host)

    Decidir conforme DESIGN.md §2.4.
    """

    async def start(self) -> None:
        """Começa a escutar eventos físicos (open serial, subscribe MQTT, etc)."""
        ...

    async def send_feedback(self, peripheral: Peripheral, command: dict) -> None:
        """
        Comando do servidor pro periférico — ex: ligar LED verde, vibrar.
        Opcional; nem todo periférico tem saída.
        """
        ...

    async def aclose(self) -> None: ...
