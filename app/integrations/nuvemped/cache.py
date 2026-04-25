"""
Cache simples em arquivo JSON com TTL.

Uso esperado:
  cache.set("current_class:prof-01:2026-...", {"turma": "9A", ...})
  cache.get("current_class:prof-01:2026-...")  # -> Optional[valor] (se não existe ou expirou)

- Em memória durante a execução (dict).
- Persiste em arquivo a cada escrita (consistência simples).
- Lock por instância para writes concorrentes.
- Serialização: json.dumps. Valores devem ser JSON-serializáveis.
  (Os DTOs são convertidos com dataclasses.asdict antes de cachear.)
"""
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


class FileCache:
    def __init__(self, path: Union[str, Path], default_ttl: int = 3600) -> None:
        self._path = Path(path)
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    # ---------- public API ----------

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            if self._is_expired(entry):
                # limpa entrada expirada preguiçosamente
                del self._data[key]
                self._flush_unlocked()
                return None
            return entry["value"]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl if ttl is not None else self._default_ttl
        with self._lock:
            self._data[key] = {
                "value": value,
                "stored_at": time.time(),
                "ttl": ttl,
            }
            self._flush_unlocked()

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._flush_unlocked()

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = len(self._data)
            expired = sum(1 for e in self._data.values() if self._is_expired(e))
            return {
                "path": str(self._path),
                "entries": total,
                "expired": expired,
            }

    # ---------- internals ----------

    @staticmethod
    def _is_expired(entry: dict[str, Any]) -> bool:
        return (time.time() - entry["stored_at"]) > entry["ttl"]

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            self._data = json.loads(raw) if raw.strip() else {}
            logger.info(f"[FileCache] Carregado {len(self._data)} entradas de {self._path}")
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"[FileCache] Falha ao ler {self._path}: {e}. Iniciando vazio.")
            self._data = {}

    def _flush_unlocked(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(self._path.suffix + ".tmp")
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._path)
        except OSError as e:
            logger.warning(f"[FileCache] Falha ao persistir {self._path}: {e}")
