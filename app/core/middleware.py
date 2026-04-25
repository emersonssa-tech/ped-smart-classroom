"""
Middleware de autenticação por API key.

Comportamento:
  - Se settings.api_key for None: sistema público (default — bom pra dev).
  - Se settings.api_key for setada (ex: env var API_KEY="abc123"):
    todo request precisa de header `X-API-Key: abc123`, exceto rotas
    listadas em settings.public_paths.

Bem simples de propósito. Pra cenário de teste piloto basta.
Pra produção real considerar JWT por usuário.
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse

from .config import get_settings


async def api_key_middleware(request: Request, call_next):
    settings = get_settings()
    if not settings.api_key:
        return await call_next(request)  # sem proteção configurada

    path = request.url.path
    public = [p.strip() for p in settings.public_paths.split(",") if p.strip()]
    if any(path == p or path.startswith(p + "/") or path.startswith(p) for p in public):
        return await call_next(request)

    sent = request.headers.get("x-api-key")
    if sent != settings.api_key:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Missing or invalid X-API-Key header"},
        )
    return await call_next(request)
