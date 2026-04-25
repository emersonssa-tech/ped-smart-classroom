"""
STT passthrough: a entrada JÁ é a transcrição.
Serve hoje porque estamos simulando áudio via string.
"""


class PassthroughSTT:
    async def transcribe(self, audio_input: str) -> str:
        # Não fazer nada — só devolver. Mantemos o async para que
        # a substituição por um STT real (I/O-bound) seja transparente.
        return audio_input.strip()

    async def aclose(self) -> None:
        return None
