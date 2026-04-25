"""
Agrega todos os subscribers do pacote integrations.

- nuvemped.handlers: on_teacher_detected, on_class_started
- placeholder (panel): on_class_started, on_content_loaded
"""
from .nuvemped import (
    ClassInfo,
    NuvemPedClient,
    get_nuvemped_client,
    register_subscribers as _register_nuvemped_subs,
)
from .placeholder import register_subscribers as _register_panel_subs


def register_subscribers() -> None:
    _register_nuvemped_subs()
    _register_panel_subs()


__all__ = [
    "register_subscribers",
    "ClassInfo",
    "NuvemPedClient",
    "get_nuvemped_client",
]
