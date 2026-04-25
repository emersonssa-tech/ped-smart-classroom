# Retomada — PED Smart Classroom

## O que tá implementado e funcionando

- **classroom_engine** — detecção de professor, lookup de aula, eventos
- **integrations/nuvemped** — client com timeout, retry, cache, fallback
- **voice_engine** — regras (regex) com 9 intents; rota `/voice/command`
- **voice_ai** — LLM com fallback automático pras regras; rota `/voice-ai/command`
- **analytics** — SQLite, métricas de uso; rotas `/analytics/{system,teacher,class,events}`
- **telemetry** — observabilidade comparativa LLM vs regras (shadow mode); rotas `/telemetry/voice/{summary,recent,disagreements,unrecognized}`
- **memory** — aprendizado contextual (correções + histórico); rotas `/memory/{correct,snapshot,preview,clear}`
- **companion** — RASCUNHO (não montado em main.py, ver `app/companion/DESIGN.md`)

## Como rodar

```bash
unzip ped-smart-classroom.zip
cd ped-smart-classroom
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abrir no navegador:
- `http://localhost:8000/docs` — Swagger com TODOS os endpoints
- `http://localhost:8000/ui/` — display de sala (frontend vanilla)
- `http://localhost:8000/health` — health check

## Pendente (pra próxima sessão)

1. **Companion** — decidir hardware/transport conforme `app/companion/DESIGN.md` §2
2. **`class_ended` automático** — hoje só dá pra disparar manualmente via `/classroom/end-class`. Auto-detecção (timeout, novo professor entrando) está como TODO no analytics
3. **Frontend** dos novos módulos — analytics/telemetria/memory só têm endpoints, sem dashboard

## Como retomar comigo num chat novo

Cole isso lá:

> Tô retomando o PED Smart Classroom. Vou anexar o zip. Os módulos
> classroom_engine, voice_engine, voice_ai, analytics, telemetry e
> memory estão prontos e testados. companion é rascunho. Quero
> [QUE VOCÊ QUER FAZER].

Anexar o zip. Eu leio a estrutura e a gente segue.
