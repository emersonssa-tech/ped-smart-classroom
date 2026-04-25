"""
Cliente Whisper via HTTP (stub).

Quando implementar:
  1. Receber base64 de áudio em audio_input
  2. POST {base_url}/audio/transcriptions com multipart file=...
  3. Retornar data['text']

Formato de API: OpenAI-compat Whisper (funciona com OpenAI, Groq Whisper,
faster-whisper-server local, etc).
"""
import base64
from io import BytesIO

import httpx


class WhisperHTTPSTT:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "whisper-1",
        timeout: float = 15.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        )

    async def transcribe(self, audio_input: str) -> str:
        # TODO Etapa futura:
        # audio_bytes = base64.b64decode(audio_input)
        # files = {"file": ("audio.wav", BytesIO(audio_bytes), "audio/wav")}
        # data = {"model": self._model, "language": "pt"}
        # r = await self._http.post("/audio/transcriptions", files=files, data=data)
        # r.raise_for_status()
        # return r.json()["text"]
        raise NotImplementedError(
            "WhisperHTTPSTT ainda não implementado. Use PassthroughSTT por enquanto."
        )

    async def aclose(self) -> None:
        await self._http.aclose()
