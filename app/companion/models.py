"""
Modelos tentativos do companion. RASCUNHO — espera-se que mudem.

Quando o módulo for implementado de fato, estes provavelmente migram pra
dataclasses estáveis (domínio interno) + Pydantic nas bordas (API), no
mesmo padrão do analytics/voice_ai.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional


CompanionMode = Literal["standby", "mirror", "companion", "activity"]
"""
- standby   : nada de aula rodando; tela de espera
- mirror    : mostra o mesmo que o projetor
- companion : mostra conteúdo paralelo (vídeo, glossário, etc)
- activity  : abriu uma atividade pro aluno responder
"""


@dataclass
class Companion:
    """Um tablet conectado."""
    device_id: str                       # UUID do tablet
    classroom_id: str
    student_id: Optional[str] = None        # null se ainda não identificado
    mode: CompanionMode = "standby"
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: Optional[datetime] = None


@dataclass
class Peripheral:
    """Um Arduino/ESP conectado a um tablet (ou à sala inteira)."""
    device_id: str
    classroom_id: str
    companion_id: Optional[str] = None      # se está pareado com tablet específico
    capabilities: list[str] = field(default_factory=list)  # ["button", "rfid", "led"]
    last_seen: Optional[datetime] = None


@dataclass
class ContentPacket:
    """Conteúdo a ser empurrado pro tablet."""
    correlation_id: str
    target_device_id: Optional[str]         # None = broadcast pra sala
    classroom_id: str
    mode: CompanionMode
    payload: dict[str, Any]              # estrutura depende do mode (ver DESIGN.md)
    pushed_at: datetime = field(default_factory=datetime.utcnow)
