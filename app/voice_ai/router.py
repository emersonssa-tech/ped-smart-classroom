from fastapi import APIRouter, status

from .factory import get_voice_ai_processor
from .schemas import VoiceCommandAIRequest, VoiceCommandAIResponse

router = APIRouter(prefix="/voice-ai", tags=["voice-ai"])


@router.post(
    "/command",
    response_model=VoiceCommandAIResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Interpreta comando de voz via LLM (com fallback pra regras)",
)
async def voice_ai_command(payload: VoiceCommandAIRequest) -> VoiceCommandAIResponse:
    processor = get_voice_ai_processor()
    return await processor.process_voice_command(payload)
