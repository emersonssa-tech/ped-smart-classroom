"""
Contrato de um cliente Speech-to-Text.

Hoje o sistema usa PassthroughSTT (o próprio texto já é a transcrição).
Amanhã entra WhisperHTTPSTT ou similar — trocando 1 linha no factory.
"""
from typing import Protocol


class STTClient(Protocol):
    async def transcribe(self, audio_input: str) -> str:
        """
        Recebe áudio (ou string simulando) e retorna transcrição em texto.
        O formato de audio_input depende da implementação:
         - passthrough: já é o texto
         - whisper:     base64 de WAV/MP3
        """
        ...

    async def aclose(self) -> None:
        """Libera recursos (connection pool, etc)."""
        ...
