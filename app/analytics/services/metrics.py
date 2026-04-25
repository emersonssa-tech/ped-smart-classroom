"""
Funções de métricas — composição das primitivas do storage.

Implementa as 3 funções pedidas:
  - get_teacher_performance(teacher_id)
  - get_class_usage(classroom_id)
  - get_system_metrics()

Cada uma retorna um dict pronto pra serializar como JSON. As queries
brutas vivem no storage; aqui só compomos.
"""
from typing import Any

from ..models import EventType
from ..storage import AnalyticsStorage


class MetricsService:
    def __init__(self, storage: AnalyticsStorage) -> None:
        self._storage = storage

    # ---------- por professor ----------

    async def get_teacher_performance(self, teacher_id: str) -> dict[str, Any]:
        counts = await self._storage.count_by_type(teacher_id=teacher_id)
        durations = await self._storage.class_durations(teacher_id=teacher_id)

        # Sessões finalizadas (com duração)
        finished = [d for d in durations if d.get("duration_minutes") is not None]
        ongoing = [d for d in durations if d.get("duration_minutes") is None]

        total_minutes = sum(d["duration_minutes"] for d in finished)
        avg_minutes = (total_minutes / len(finished)) if finished else 0.0

        # Voice commands desse professor: pegar últimos pra extrair intents do metadata
        voice_events = await self._storage.query(
            event_type=EventType.VOICE_COMMAND,
            teacher_id=teacher_id,
            limit=500,
        )
        intents_breakdown: dict[str, int] = {}
        for v in voice_events:
            intent = (v.get("metadata") or {}).get("intent")
            if intent:
                intents_breakdown[intent] = intents_breakdown.get(intent, 0) + 1

        # Última atividade
        recent_any = await self._storage.query(teacher_id=teacher_id, limit=1)
        last_active = recent_any[0]["timestamp"] if recent_any else None

        return {
            "teacher_id": teacher_id,
            "total_classes_started": counts.get(EventType.CLASS_STARTED, 0),
            "total_classes_ended":   counts.get(EventType.CLASS_ENDED, 0),
            "ongoing_classes":       len(ongoing),
            "total_class_minutes":   round(total_minutes, 1),
            "avg_class_minutes":     round(avg_minutes, 1),
            "total_voice_commands":  counts.get(EventType.VOICE_COMMAND, 0),
            "total_slide_changes":   counts.get(EventType.SLIDE_CHANGED, 0),
            "total_activities_opened": counts.get(EventType.ACTIVITY_OPENED, 0),
            "intents_breakdown":     dict(sorted(intents_breakdown.items(), key=lambda kv: -kv[1])),
            "last_active":           last_active,
            "recent_sessions":       finished[:10],   # 10 últimas finalizadas
        }

    # ---------- por sala/turma ----------

    async def get_class_usage(self, classroom_id: str) -> dict[str, Any]:
        counts = await self._storage.count_by_type(classroom_id=classroom_id)
        durations = await self._storage.class_durations(classroom_id=classroom_id)
        finished = [d for d in durations if d.get("duration_minutes") is not None]

        # professores únicos
        teachers = {d["teacher_id"] for d in durations if d.get("teacher_id")}

        return {
            "classroom_id": classroom_id,
            "total_sessions":   counts.get(EventType.CLASS_STARTED, 0),
            "total_minutes":    round(sum(d["duration_minutes"] for d in finished), 1),
            "unique_teachers":  len(teachers),
            "teachers":         sorted(teachers),
            "voice_commands":   counts.get(EventType.VOICE_COMMAND, 0),
            "slide_changes":    counts.get(EventType.SLIDE_CHANGED, 0),
            "activities_opened": counts.get(EventType.ACTIVITY_OPENED, 0),
            "ongoing_sessions": len(durations) - len(finished),
        }

    # ---------- visão de sistema ----------

    async def get_system_metrics(self) -> dict[str, Any]:
        counts = await self._storage.count_by_type()
        durations = await self._storage.class_durations()
        ongoing = [d for d in durations if d.get("duration_minutes") is None]
        finished = [d for d in durations if d.get("duration_minutes") is not None]
        total_minutes = sum(d["duration_minutes"] for d in finished)

        top_teachers = await self._storage.top_field("teacher_id", limit=10)
        top_classrooms = await self._storage.top_field("classroom_id", limit=10)
        daily = await self._storage.daily_counts(days=7)

        # rearranja daily como [{date, totals: {event_type: n}}]
        by_date: dict[str, dict[str, int]] = {}
        for row in daily:
            by_date.setdefault(row["date"], {})[row["event_type"]] = row["n"]
        daily_usage = [{"date": d, "totals": v} for d, v in sorted(by_date.items(), reverse=True)]

        total_events = sum(counts.values())

        return {
            "total_events": total_events,
            "events_by_type": counts,
            "active_classes_now": len(ongoing),
            "total_class_minutes_finished": round(total_minutes, 1),
            "daily_usage_last_7": daily_usage,
            "top_teachers":   top_teachers,
            "top_classrooms": top_classrooms,
        }
