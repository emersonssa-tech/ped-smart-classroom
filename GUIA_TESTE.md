# Guia de Teste — PED Smart Classroom

Como rodar local e testar comandos de voz por curl/Postman.
Testado em Python 3.11+ e 3.12.

---

## 1. Setup (uma vez só)

```bash
cd ped-smart-classroom
python -m venv .venv
source .venv/bin/activate              # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Rodar o servidor

```bash
uvicorn app.main:app --reload
```

Você verá nos logs:
```
[NuvemPed] Cliente http=http://localhost:8001 ...
[Analytics] SQLite pronto em .analytics/events.db
[Telemetry] inicializada em .telemetry/voice.jsonl
[Memory] inicializada em memory/memory_store.json
Subscribers de eventos registrados.
Application startup complete.
```

> **Importante:** o servidor tenta a NuvemPed em `localhost:8001`. Se o
> fake não estiver rodando, **não tem problema** — o sistema cai em modo
> degradado e tudo funciona, exceto buscar a aula real do horário.

Aberto em **http://localhost:8000**:

- `http://localhost:8000/docs` — Swagger UI (testa direto pelo browser)
- `http://localhost:8000/ui/` — frontend simulando o display da sala

---

## 3. Testar VOZ (regras puras — sem LLM, sem dependência externa)

Funciona sempre. **9 intents** mapeados a partir de regex tolerante.

```bash
# Comando reconhecido
curl -X POST http://localhost:8000/voice/command \
  -H 'Content-Type: application/json' \
  -d '{"text":"próximo slide", "teacher_id":"prof-01", "classroom_id":"sala-7"}'

# Resposta: {"recognized":true, "intent":"next_slide", "confidence":0.95, ...}
```

### Tabela de comandos pra testar

| Texto                         | Intent esperado     |
|-------------------------------|---------------------|
| "começar aula"                | start_class         |
| "próximo slide" / "passa"     | next_slide          |
| "slide anterior" / "volta"    | previous_slide      |
| "abrir atividade 3"           | open_activity (id=3)|
| "tocar vídeo"                 | play_video          |
| "pausar vídeo"                | pause_video         |
| "fazer chamada"               | mark_attendance     |
| "ligar projetor"              | turn_on_projector   |
| "desligar projetor"           | turn_off_projector  |
| "blablabla"                   | null (unrecognized) |

### Pelo Swagger
1. Abre `http://localhost:8000/docs`
2. Vai em **POST /voice/command** → "Try it out"
3. Cola um JSON do tipo `{"text":"abrir atividade 3","teacher_id":"prof-01","classroom_id":"sala-7"}`
4. Executa e vê o resultado

---

## 4. Testar VOZ COM LLM (precisa API key)

Configura uma das duas no `.env` (ou export):

```bash
export VOICE_AI_API_KEY="sua-key-aqui"
export VOICE_AI_PROVIDER="anthropic"   # ou "openai"
export VOICE_AI_MODEL="claude-3-5-haiku-latest"   # ou "gpt-4o-mini"
export VOICE_AI_MODE="auto"            # auto | online | offline
```

Reinicia o `uvicorn`. Aí:

```bash
curl -X POST http://localhost:8000/voice-ai/command \
  -H 'Content-Type: application/json' \
  -d '{"audio_input":"qual aula está acontecendo agora", "teacher_id":"prof-01"}'

# Resposta esperada: intent=query_current_class, source=llm
# (esse intent só o LLM reconhece — regras retornam null)
```

**Sem API key configurada**: o sistema **não quebra** — automaticamente
roda em offline, usando regras. `source` no response vai virar `"rules"`.

---

## 5. Aprendizado contextual (memory)

### Registrar uma correção
```bash
curl -X POST http://localhost:8000/memory/correct \
  -H 'Content-Type: application/json' \
  -d '{"input":"passa aí", "correct_intent":"next_slide", "teacher_id":"prof-01"}'
```

### Ver o que está salvo
```bash
curl http://localhost:8000/memory/snapshot
```

### Aplicar a correção (offline → override automático)
```bash
curl -X POST http://localhost:8000/voice-ai/command \
  -H 'Content-Type: application/json' \
  -d '{"audio_input":"passa aí", "teacher_id":"prof-01"}'

# Resposta: source=memory, intent=next_slide
```

### Preview do que seria injetado no prompt do LLM
```bash
curl 'http://localhost:8000/memory/preview?input=próximo'
```

Mostra `exact_correction` (se houver match exato) e `few_shot_examples`
(exemplos similares que entrariam no prompt).

---

## 6. Analytics — métricas de uso

Depois de ter feito alguns comandos:

```bash
# Visão geral do sistema
curl http://localhost:8000/analytics/system | jq

# Performance de um professor
curl http://localhost:8000/analytics/teacher/prof-01 | jq

# Uso de uma sala
curl http://localhost:8000/analytics/class/sala-7 | jq

# Eventos brutos (debug)
curl 'http://localhost:8000/analytics/events?event_type=voice_command&limit=10' | jq
```

> **Para ter duração de aula calculada:** precisa publicar `class_started`
> (vem da NuvemPed real ou do fake) e depois encerrar com:
>
> ```bash
> curl -X POST http://localhost:8000/classroom/end-class \
>   -H 'Content-Type: application/json' \
>   -d '{"correlation_id":"<id-da-aula>", "teacher_id":"prof-01", "classroom_id":"sala-7"}'
> ```

---

## 7. Telemetria — accuracy LLM vs regras

Só fica interessante quando você está em modo online (com API key).

```bash
# Resumo: contagens, latências, agreement
curl http://localhost:8000/telemetry/voice/summary | jq

# Casos onde LLM e regras divergiram (queue de aprendizado)
curl http://localhost:8000/telemetry/voice/disagreements | jq

# Comandos que ninguém entendeu (queue de melhoria)
curl http://localhost:8000/telemetry/voice/unrecognized | jq

# Últimos N comandos
curl 'http://localhost:8000/telemetry/voice/recent?limit=20' | jq
```

Categorias de "agreement" no resumo:
- `match` — LLM e regras concordaram totalmente
- `match_intent_only` — mesmo intent, entities diferentes
- `rules_subset` — LLM extraiu mais info que regras (ganho do LLM)
- `disagree` — intents diferentes
- `llm_only` — regras = nada, LLM = algo (ganho do LLM)
- `rules_only` — LLM = nada, regras = algo (regressão do LLM)

---

## 8. Postman: importar como collection

Cria uma collection no Postman e adiciona:

```
POST {{base_url}}/voice/command
POST {{base_url}}/voice-ai/command
POST {{base_url}}/memory/correct
GET  {{base_url}}/memory/snapshot
GET  {{base_url}}/memory/preview?input=passa aí
GET  {{base_url}}/analytics/system
GET  {{base_url}}/analytics/teacher/prof-01
GET  {{base_url}}/analytics/class/sala-7
GET  {{base_url}}/telemetry/voice/summary
POST {{base_url}}/classroom/end-class
```

`base_url = http://localhost:8000`

---

## 9. O que verificar ao testar

✅ `POST /voice/command` retorna 202 com intent reconhecido
✅ `POST /voice-ai/command` em offline funciona e retorna `source=rules`
✅ Após `POST /memory/correct`, o input corrigido vira `source=memory`
✅ `GET /analytics/system` mostra contagens crescendo a cada comando
✅ Logs do uvicorn mostram cada evento sendo publicado no event_bus
✅ Arquivos persistidos: `.analytics/events.db`, `.telemetry/voice.jsonl`,
   `memory/memory_store.json`

## 10. Troubleshooting

**"NuvemPed unavailable"** nos logs → normal, o servidor fake não está rodando.
Tudo continua funcionando exceto a busca de horário real.

**`source=rules` mesmo querendo LLM** → faltou API key, sistema cai em offline
automático. Veja seção 4.

**Voz reconhecida mas analytics não conta** → faltou enviar `teacher_id`
no payload do comando.

**Memory não está aplicando override** → confira se `memory_lookup_enabled=true`
nas settings (default é `true`). E lembre que override exato só age em
modo `offline` por design — em online, a memória entra no prompt do LLM.
