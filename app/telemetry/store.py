"""
TelemetryStore — JSONL append-only no disco + cache in-memory.

Decisões:
  - JSONL: 1 linha por evento, append atômico, fácil de inspecionar/grepar.
  - asyncio.Lock no append para serializar writes (evita linhas truncadas).
  - Memory cache reconstruído na inicialização lendo o arquivo todo.
    Suficiente até ~100k linhas; depois disso vale trocar por SQLite.
  - Sem rotação de arquivo nesta etapa (futuro: rotate diário ou por tamanho).
"""
import asyncio
import json
import logging
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Union

logger = logging.getLogger(__name__)


class TelemetryStore:
    def __init__(
        self,
        path: Union[str, Path],
        recent_buffer_size: int = 500,
    ) -> None:
        self._path = Path(path)
        self._lock = asyncio.Lock()
        # buffer circular dos N mais recentes (pra endpoint /recent sem reler arquivo)
        self._recent: deque[dict[str, Any]] = deque(maxlen=recent_buffer_size)
        # contadores agregados — atualizados a cada append
        self._counts: dict[str, int] = {
            "total": 0,
            "by_source_rules": 0,
            "by_source_llm": 0,
            "by_mode_online": 0,
            "by_mode_offline": 0,
            "with_warning": 0,
            "recognized": 0,
            "unrecognized": 0,
        }
        self._by_intent: dict[str, int] = {}
        self._by_agreement: dict[str, int] = {}
        self._latency_sum_ms: int = 0
        self._latency_count: int = 0
        self._load_existing()

    # ---------- public API ----------

    async def record(self, event: dict[str, Any]) -> None:
        """Append + atualiza in-memory. Thread/task-safe."""
        async with self._lock:
            self._update_aggregates(event)
            self._recent.append(event)
            self._append_to_disk(event)

    def summary(self) -> dict[str, Any]:
        avg_lat = (self._latency_sum_ms / self._latency_count) if self._latency_count else 0.0
        return {
            "counts": dict(self._counts),
            "by_intent": dict(sorted(self._by_intent.items(), key=lambda kv: -kv[1])),
            "by_agreement": dict(sorted(self._by_agreement.items(), key=lambda kv: -kv[1])),
            "avg_latency_ms": round(avg_lat, 1),
            "samples_for_latency": self._latency_count,
        }

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        n = max(1, min(limit, self._recent.maxlen or limit))
        return list(self._recent)[-n:]

    def disagreements(self, limit: int = 50) -> list[dict[str, Any]]:
        out = []
        for e in reversed(self._recent):
            shadow = e.get("shadow") or {}
            agreement = shadow.get("agreement")
            if agreement and agreement != "match":
                out.append(e)
                if len(out) >= limit:
                    break
        return out

    def unrecognized(self, limit: int = 50) -> list[dict[str, Any]]:
        out = []
        for e in reversed(self._recent):
            if e.get("intent") is None:
                out.append({
                    "ts": e.get("ts"),
                    "transcript": e.get("transcript"),
                    "source": e.get("source"),
                    "mode": e.get("mode"),
                })
                if len(out) >= limit:
                    break
        return out

    async def clear(self) -> None:
        """Apaga arquivo e zera memória (uso dev/teste)."""
        async with self._lock:
            self._recent.clear()
            for k in self._counts:
                self._counts[k] = 0
            self._by_intent.clear()
            self._by_agreement.clear()
            self._latency_sum_ms = 0
            self._latency_count = 0
            try:
                if self._path.exists():
                    self._path.unlink()
            except OSError as exc:
                logger.warning(f"[Telemetry] falha ao apagar {self._path}: {exc}")

    # ---------- internals ----------

    def _update_aggregates(self, event: dict[str, Any]) -> None:
        self._counts["total"] += 1
        source = event.get("source") or "unknown"
        mode = event.get("mode") or "unknown"
        intent = event.get("intent")
        latency = event.get("latency_ms")
        warning = event.get("warning")
        shadow = event.get("shadow") or {}

        if source == "rules":
            self._counts["by_source_rules"] += 1
        elif source == "llm":
            self._counts["by_source_llm"] += 1
        if mode == "online":
            self._counts["by_mode_online"] += 1
        elif mode == "offline":
            self._counts["by_mode_offline"] += 1
        if warning:
            self._counts["with_warning"] += 1

        if intent is None:
            self._counts["unrecognized"] += 1
            self._by_intent["__unrecognized__"] = self._by_intent.get("__unrecognized__", 0) + 1
        else:
            self._counts["recognized"] += 1
            self._by_intent[intent] = self._by_intent.get(intent, 0) + 1

        if isinstance(latency, (int, float)):
            self._latency_sum_ms += int(latency)
            self._latency_count += 1

        if shadow.get("agreement"):
            ag = shadow["agreement"]
            self._by_agreement[ag] = self._by_agreement.get(ag, 0) + 1

    def _append_to_disk(self, event: dict[str, Any]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning(f"[Telemetry] falha ao escrever {self._path}: {exc}")

    def _load_existing(self) -> None:
        if not self._path.exists():
            return
        try:
            with self._path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self._update_aggregates(e)
                    self._recent.append(e)
            logger.info(
                f"[Telemetry] carregado {self._counts['total']} entradas de {self._path}"
            )
        except OSError as exc:
            logger.warning(f"[Telemetry] falha ao ler {self._path}: {exc}")


def utcnow_iso() -> str:
    return datetime.utcnow().isoformat()
