from fastapi import APIRouter, status

from .schemas import VoiceCommandRequest, VoiceCommandResponse
from .service import service

router = APIRouter(prefix="/voice", tags=["voice-engine"])


@router.post(
    "/command",
    response_model=VoiceCommandResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Interpreta um comando de voz em texto e dispara o evento correspondente",
)
async def voice_command(payload: VoiceCommandRequest) -> VoiceCommandResponse:
    return await service.handle_command(payload)
