from .factory import get_voice_ai_processor
from .processor import INTENT_TO_EVENT, VoiceAIProcessor
from .router import router
from .schemas import VoiceCommandAIRequest, VoiceCommandAIResponse
from typing import Optional

__all__ = [
    "router",
    "get_voice_ai_processor",
    "VoiceAIProcessor",
    "VoiceCommandAIRequest",
    "VoiceCommandAIResponse",
    "INTENT_TO_EVENT",
    "process_voice_command",
]


async def process_voice_command(audio_input: str, classroom_id: Optional[str] = None):
    """
    API pedida pela spec: audio_input (str) → intent_response.

    Conveniência sobre VoiceAIProcessor.process_voice_command().
    """
    processor = get_voice_ai_processor()
    return await processor.process_voice_command(
        VoiceCommandAIRequest(audio_input=audio_input, classroom_id=classroom_id)
    )
