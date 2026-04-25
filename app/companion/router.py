"""
Endpoints stub do companion.

Retornam 501 Not Implemented com mensagem útil — quem chamar sabe que
o módulo está em rascunho. Não é montado em main.py ainda; quando for,
basta `app.include_router(companion_router)`.
"""
from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/companion", tags=["companion (rascunho)"])


_NOT_IMPL_MSG = (
    "Módulo companion ainda não implementado — ver app/companion/DESIGN.md "
    "para decisões em aberto."
)


@router.post(
    "/peripheral/event",
    summary="(stub) Recebe evento de periférico físico (Arduino/ESP)",
)
async def peripheral_event() -> dict:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, _NOT_IMPL_MSG)


@router.get(
    "/devices",
    summary="(stub) Lista companions conectados",
)
async def list_devices() -> dict:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, _NOT_IMPL_MSG)


# WS endpoint não pode ser stub fácil; quando implementar, criar
# como @router.websocket("/ws/{device_id}") chamando o CompanionTransport.
