"""
Implementação SQLite do AnalyticsStorage.

- 1 conexão global, escritas serializadas via asyncio.Lock.
- WAL mode pra reads concorrentes não bloquearem.
- Operações síncronas envoltas em asyncio.to_thread.
- Schema definido aqui (CREATE TABLE IF NOT EXISTS no init).

SQL escrito à mão pra portabilidade futura ao Postgres — apenas
julianday() é específico de SQLite (calcula duração). No Postgres
isso vira EXTRACT(EPOCH FROM ...).
"""
import asyncio
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Optional, Union

from ..models import AnalyticsEvent

logger = logging.getLogger(__name__)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    correlation_id TEXT,
    teacher_id TEXT,
    classroom_id TEXT,
    timestamp TEXT NOT NULL,
    metadata TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_teacher ON events(teacher_id);
CREATE INDEX IF NOT EXISTS idx_events_classroom ON events(classroom_id);
CREATE INDEX IF NOT EXISTS idx_events_correlation ON events(correlation_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
"""


class SQLiteAnalyticsStorage:
    def __init__(self, path: Union[str, Path]) -> None:
        self._path = Path(path)
        self._lock = asyncio.Lock()
        self._initialized = False

    # ---------- ciclo de vida ----------

    async def init(self) -> None:
        if self._initialized:
            return
        await asyncio.to_thread(self._init_sync)
        self._initialized = True

    def _init_sync(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            for stmt in _SCHEMA.strip().split(";"):
                if stmt.strip():
                    conn.execute(stmt)
            conn.commit()
        logger.info(f"[Analytics] SQLite pronto em {self._path}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path), isolation_level=None)  # autocommit
        conn.row_factory = sqlite3.Row
        return conn

    async def aclose(self) -> None:
        return None  # conexões são por-chamada

    # ---------- escrita ----------

    async def record(self, event: AnalyticsEvent) -> None:
        async with self._lock:
            await asyncio.to_thread(self._record_sync, event)

    def _record_sync(self, event: AnalyticsEvent) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO events (event_type, correlation_id, teacher_id,
                                    classroom_id, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_type,
                    event.correlation_id,
                    event.teacher_id,
                    event.classroom_id,
                    event.timestamp,
                    json.dumps(event.metadata, ensure_ascii=False) if event.metadata else None,
                ),
            )

    # ---------- leitura ----------

    async def query(
        self,
        *,
        event_type: Optional[str] = None,
        teacher_id: Optional[str] = None,
        classroom_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(
            self._query_sync,
            event_type, teacher_id, classroom_id, correlation_id, since, until, limit,
        )

    def _query_sync(
        self,
        event_type, teacher_id, classroom_id, correlation_id, since, until, limit,
    ) -> list[dict[str, Any]]:
        clauses, params = [], []
        if event_type:
            clauses.append("event_type = ?"); params.append(event_type)
        if teacher_id:
            clauses.append("teacher_id = ?"); params.append(teacher_id)
        if classroom_id:
            clauses.append("classroom_id = ?"); params.append(classroom_id)
        if correlation_id:
            clauses.append("correlation_id = ?"); params.append(correlation_id)
        if since:
            clauses.append("timestamp >= ?"); params.append(since)
        if until:
            clauses.append("timestamp <= ?"); params.append(until)

        sql = "SELECT * FROM events"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    async def count_by_type(
        self,
        *,
        teacher_id: Optional[str] = None,
        classroom_id: Optional[str] = None,
        since: Optional[str] = None,
    ) -> dict[str, int]:
        return await asyncio.to_thread(
            self._count_by_type_sync, teacher_id, classroom_id, since
        )

    def _count_by_type_sync(self, teacher_id, classroom_id, since) -> dict[str, int]:
        clauses, params = [], []
        if teacher_id:
            clauses.append("teacher_id = ?"); params.append(teacher_id)
        if classroom_id:
            clauses.append("classroom_id = ?"); params.append(classroom_id)
        if since:
            clauses.append("timestamp >= ?"); params.append(since)

        sql = "SELECT event_type, COUNT(*) AS n FROM events"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " GROUP BY event_type"

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return {r["event_type"]: r["n"] for r in rows}

    async def class_durations(
        self,
        *,
        teacher_id: Optional[str] = None,
        classroom_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(
            self._class_durations_sync, teacher_id, classroom_id
        )

    def _class_durations_sync(self, teacher_id, classroom_id) -> list[dict[str, Any]]:
        clauses, params = ["s.event_type = 'class_started'"], []
        if teacher_id:
            clauses.append("s.teacher_id = ?"); params.append(teacher_id)
        if classroom_id:
            clauses.append("s.classroom_id = ?"); params.append(classroom_id)

        # LEFT JOIN: aulas sem class_ended ainda aparecem (com ended_at=NULL)
        sql = f"""
            SELECT
                s.correlation_id,
                s.teacher_id,
                s.classroom_id,
                s.timestamp AS started_at,
                e.timestamp AS ended_at,
                CASE
                    WHEN e.timestamp IS NULL THEN NULL
                    ELSE (julianday(e.timestamp) - julianday(s.timestamp)) * 24 * 60
                END AS duration_minutes
            FROM events s
            LEFT JOIN events e
                ON e.correlation_id = s.correlation_id
                AND e.event_type = 'class_ended'
            WHERE {' AND '.join(clauses)}
            ORDER BY s.timestamp DESC
        """
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    async def daily_counts(self, *, days: int = 7) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._daily_counts_sync, days)

    def _daily_counts_sync(self, days: int) -> list[dict[str, Any]]:
        sql = """
            SELECT
                substr(timestamp, 1, 10) AS date,
                event_type,
                COUNT(*) AS n
            FROM events
            WHERE timestamp >= date('now', ?)
            GROUP BY date, event_type
            ORDER BY date DESC
        """
        with self._connect() as conn:
            rows = conn.execute(sql, (f"-{days} days",)).fetchall()
        return [dict(r) for r in rows]

    async def top_field(
        self,
        field: str,
        *,
        event_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._top_field_sync, field, event_type, limit)

    def _top_field_sync(self, field, event_type, limit) -> list[dict[str, Any]]:
        if field not in {"teacher_id", "classroom_id", "correlation_id"}:
            raise ValueError(f"campo inválido: {field}")  # whitelist anti-injeção
        clauses = [f"{field} IS NOT NULL"]
        params = []
        if event_type:
            clauses.append("event_type = ?"); params.append(event_type)
        sql = (
            f"SELECT {field} AS value, COUNT(*) AS n FROM events "
            f"WHERE {' AND '.join(clauses)} "
            f"GROUP BY {field} ORDER BY n DESC LIMIT ?"
        )
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # ---------- helpers ----------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        meta = d.get("metadata")
        if meta:
            try:
                d["metadata"] = json.loads(meta)
            except (TypeError, ValueError):
                pass
        return d
