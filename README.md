# PED Smart Classroom — Etapa 6

Backend FastAPI com **detecção de rosto via webcam** (OpenCV + Haar Cascade),
rodando em thread de background, publicando eventos no event bus saga.

Reconhecimento facial (identificar *quem* é o professor) fica pra próxima etapa.

## Rodar

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edite .env e coloque CAMERA_ENABLED=true se quiser usar webcam
uvicorn app.main:app --reload
```

Abrir `http://localhost:8000/ui/` (display) ou `/docs` (Swagger).

## Novo módulo `app/vision/`

```
app/vision/
├── face_detector.py   # classe pura: recebe np.array, retorna bboxes
├── worker.py          # thread de background: câmera + loop + publish
├── lifecycle.py       # start/stop wired ao FastAPI lifespan
└── router.py          # GET /vision/status
```

Separação proposital:
- `face_detector.py` não conhece câmera — testável só com imagens
- `worker.py` orquestra câmera + detector + event_bus
- `lifecycle.py` lida com o FastAPI lifespan e falhas silenciosas
- `router.py` expõe métricas de observabilidade

## Fluxo da detecção

1. Worker abre `cv2.VideoCapture(CAMERA_INDEX)` em thread daemon
2. A cada `CAMERA_DETECTION_INTERVAL`s, captura frame e roda cascade
3. Se detectou rosto **e** passou `CAMERA_DETECTION_COOLDOWN`s desde última publicação:
   - Gera `correlation_id` novo
   - Publica `teacher_detected` no event_bus com:
     ```python
     {
       "correlation_id": "<uuid>",
       "source": "camera",
       "teacher_id": None,       # sem reconhecimento ainda
       "teacher_name": None,
       "reference_time": "<iso>",
       "num_faces": 1,
     }
     ```
4. Handlers existentes reagem:
   - `classroom_engine.on_teacher_detected`: audita no log
   - `nuvemped.on_teacher_detected`: detecta `teacher_id=None` e **pula**
     sem chamar API (preserva a cadeia pra quando houver reconhecimento)

Isso significa que a detecção só por câmera **não gera aula automaticamente**
ainda. Quando a Etapa 7 adicionar reconhecimento, o componente novo vai
preencher `teacher_id` e o resto da cadeia funciona sem alteração.

## Configuração (.env)

```bash
CAMERA_ENABLED=false              # liga/desliga — default off pra dev sem hw
CAMERA_INDEX=0                    # 0 = webcam padrão
CAMERA_FRAME_WIDTH=320            # resolução reduzida p/ performance
CAMERA_MIN_FACE_SIZE=60           # pixels; abaixo disso é ruído
CAMERA_DETECTION_INTERVAL=0.5     # segundos entre frames processados
CAMERA_DETECTION_COOLDOWN=10.0    # debounce entre eventos publicados
```

## Endpoints

| Rota | O que é |
|---|---|
| `GET /health` | Healthcheck |
| `GET /vision/status` | Status do face detector (is_running, total_detections, etc.) |
| `POST /classroom/simulate-teacher` | Simulação HTTP (ainda funciona) |
| `GET /ui/` | Display da sala |
| `GET /docs` | Swagger |

**Exemplo `/vision/status`:**
```json
{
  "enabled": true,
  "is_running": true,
  "camera_opened": true,
  "total_detections": 5,
  "last_detection_at": "2026-04-27T14:32:15.891234"
}
```

## Graceful degradation

- `CAMERA_ENABLED=false` → worker nem tenta abrir câmera
- `CAMERA_ENABLED=true` + câmera indisponível → erro logado, sistema segue funcional
- OpenCV não instalado → erro logado pedindo `pip install opencv-python-headless`, sistema segue

Nada disso derruba o servidor. O `/vision/status` sempre reflete o estado real.

## Por que Haar Cascade e não DNN?

- Vem embutido no OpenCV (`cv2.data.haarcascades`), zero download
- CPU-only, sem GPU
- Rápido em 320x240: suficiente pra 2 fps de processamento com folga
- Acurácia o bastante pra *detectar presença* (que é o escopo desta etapa)
- Para *reconhecer* quem é (Etapa 7+), aí sim DNN/face_recognition faz sentido

---

# Voice Engine

Módulo `app/voice_engine/` — interpreta comandos de voz em texto e
publica o evento correspondente no event_bus.

## Endpoint

`POST /voice/command`

```bash
curl -X POST http://localhost:8000/voice/command \
  -H 'Content-Type: application/json' \
  -d '{"text":"abrir atividade 3","classroom_id":"sala-7"}'
```

Resposta:
```json
{
  "recognized": true,
  "intent": "open_activity",
  "entities": {"activity_id": "3"},
  "confidence": 1.0,
  "normalized_text": "abrir atividade 3",
  "event_name": "voice_open_activity",
  "correlation_id": "...",
  "received_at": "..."
}
```

## Intents suportados

| Intent | Exemplos | Event publicado |
|---|---|---|
| `start_class` | "iniciar aula", "vamos começar" | `voice_start_class` |
| `next_slide` | "próximo slide", "avança", "slide seguinte" | `voice_next_slide` |
| `previous_slide` | "slide anterior", "volta o slide" | `voice_previous_slide` |
| `open_activity` | "abrir atividade 3" (entity `activity_id`) | `voice_open_activity` |
| `play_video` | "tocar vídeo", "play no vídeo", "reproduz filme" | `voice_play_video` |
| `pause_video` | "pausa o vídeo", "para o vídeo" | `voice_pause_video` |
| `mark_attendance` | "fazer chamada", "marcar presença" | `voice_mark_attendance` |
| `turn_on_projector` | "ligar projetor", "acende o projetor" | `voice_turn_on_projector` |
| `turn_off_projector` | "desligar projetor", "apaga projetor" | `voice_turn_off_projector` |
| *(nada bate)* | "blablabla", "será que dá pra jantar?" | `voice_unrecognized` |

## Arquitetura

```
app/voice_engine/
├── schemas.py         # Pydantic request/response
├── intents.py         # IntentRule declarativa (nome + patterns + event)
├── recognizer.py      # Protocol IntentRecognizer + RuleBasedIntentRecognizer + normalize
├── service.py         # orquestração (normalize → recognize → publish)
├── handlers.py        # subscribers stub (um por intent)
└── router.py          # POST /voice/command
```

Pipeline:
```
texto cru → normalize() → recognizer.recognize() → event_bus.publish() → handlers
```

**Normalização**: lowercase + strip accents + strip punctuation + collapse spaces.
Robusto a variações de transcrição ("PRÓXIMO SLIDE!" = "próximo slide" = "proximo  slide").

**Extensibilidade**: trocar `RuleBasedIntentRecognizer` por um NLP/LLM recognizer
é substituir uma linha em `recognizer.py` — o Protocol garante que nada mais muda.

**Adicionar novo intent**: acrescentar uma `IntentRule` em `intents.py`.
Nada mais precisa ser tocado.

## Função utilitária

```python
from app.voice_engine import interpret_command
interpret_command("próximo slide por favor!")
# → {"intent": "next_slide", "entities": {}}
```


---

# Voice AI (LLM)

Módulo `app/voice_ai/` — interpreta comandos via **LLM** com **fallback automático
para regras** quando o LLM falha. Coexiste com `voice_engine` (regras puras) e
publica os MESMOS eventos no event_bus.

## Estrutura

```
app/voice_ai/
├── stt/
│   ├── base.py              # Protocol STTClient
│   ├── passthrough.py       # impl atual: o texto JÁ é a transcrição
│   └── whisper_http.py      # stub Whisper (pronto pra implementar)
├── llm/
│   ├── base.py              # Protocol LLMClient + exceções (Timeout/Unavailable/Auth)
│   ├── openai_compat.py     # OpenAI / Ollama / llama.cpp / Groq / vLLM / proxies
│   └── anthropic_client.py  # Anthropic Messages API nativa
├── processor/
│   └── processor.py         # orquestração + parser tolerante + fallback
├── prompts/
│   └── intent_extraction.py # system prompt + few-shot
├── factory.py
├── router.py                # POST /voice-ai/command
└── schemas.py
```

## Exemplo de uso real

### Via Python (função pública pedida na spec)
```python
import asyncio
from app.voice_ai import process_voice_command

async def main():
    response = await process_voice_command("qual a aula agora")
    print(response.intent)         # "query_current_class" (se LLM online)
    print(response.source)         # "llm" ou "rules" (fallback)
    print(response.event_name)     # "voice_query_current_class"

asyncio.run(main())
```

### Via HTTP
```bash
curl -X POST http://localhost:8000/voice-ai/command \
  -H 'Content-Type: application/json' \
  -d '{"audio_input":"abre atividade de matemática","classroom_id":"sala-7"}'
```

Resposta:
```json
{
  "recognized": true,
  "intent": "open_activity",
  "entities": {"subject": "matemática"},   ← LLM extrai entity que regex não pega
  "confidence": 0.9,
  "transcript": "abre atividade de matemática",
  "source": "llm",
  "mode": "online",
  "event_name": "voice_open_activity",
  "latency_ms": 850,
  "warning": null
}
```

## Configuração (.env)

```bash
# Modo:
#   "auto"    → usa LLM se VOICE_AI_API_KEY estiver setada (default)
#   "online"  → força LLM (erro se sem key)
#   "offline" → só regras, nunca chama LLM
VOICE_AI_MODE=auto

# Provider:
#   "openai"    → qualquer endpoint OpenAI-compat (Ollama, Groq, llama.cpp, etc)
#   "anthropic" → API nativa Anthropic
VOICE_AI_PROVIDER=openai
VOICE_AI_BASE_URL=https://api.openai.com/v1
VOICE_AI_API_KEY=sk-...
VOICE_AI_MODEL=gpt-4o-mini
VOICE_AI_TIMEOUT=8.0
```

Para rodar com Ollama local (zero custo, totalmente offline):
```bash
VOICE_AI_BASE_URL=http://localhost:11434/v1
VOICE_AI_API_KEY=ollama          # qualquer string não-vazia
VOICE_AI_MODEL=llama3.1:8b
```

## Comportamento de fallback

| Situação | Resultado |
|---|---|
| LLM responde JSON válido com intent do catálogo | `source="llm"` |
| LLM responde JSON inválido | fallback regras, `warning` preenchido |
| LLM responde com markdown ou prosa em volta | parser pega o JSON do meio |
| LLM inventa intent fora do catálogo | rejeitado, fallback regras |
| LLM timeout/connect error | fallback regras, `warning` preenchido |
| Sem API key (auto) | nunca tenta LLM, `mode="offline"` |

## `query_current_class` — exemplo do ganho do LLM

Esse intent só existe no `voice_ai`. Regras (regex) não reconhecem, vira
`unrecognized`. LLM entende:

| Frase | voice_engine (regras) | voice_ai (LLM) |
|---|---|---|
| "qual a aula agora?" | `unrecognized` | `query_current_class` |
| "o que estamos estudando?" | `unrecognized` | `query_current_class` |
| "abre atividade de matemática" | `open_activity` (sem entity) | `open_activity` + `subject="matemática"` |

---

## Analytics

Módulo de coleta de eventos e geração de métricas de uso. Independente da
telemetria técnica — analytics responde "como os usuários estão usando?",
não "como o sistema está performando?".

### Como funciona

```
event_bus  ──→  analytics/services/collector.py  ──→  SQLite (.analytics/events.db)
                       │                                     │
                       │ mapeia voice_next_slide              │
                       │ → voice_command + slide_changed      ▼
                       │                            metrics.py (queries SQL)
                                                              │
                                                              ▼
                                              /analytics/{system,teacher,class}
```

### Modelo de dados

Tabela única `events` (event-sourcing) com `metadata` em JSON — schema
flexível, novo tipo de evento entra sem migration. Migração pra Postgres
é trocar 1 linha em `factory.py` (apenas `julianday()` é específico de
SQLite e vira `EXTRACT(EPOCH FROM ...)`).

### Eventos capturados

| Origem (event_bus)              | → Analytics                          |
| ------------------------------- | ------------------------------------ |
| `teacher_detected`              | `teacher_detected`                   |
| `class_started`                 | `class_started`                      |
| `class_ended` (via `/end-class`)| `class_ended`                        |
| `voice_next_slide`              | `voice_command` + `slide_changed`    |
| `voice_previous_slide`          | `voice_command` + `slide_changed`    |
| `voice_open_activity`           | `voice_command` + `activity_opened`  |
| outros `voice_*`                | `voice_command`                      |
| `voice_unrecognized`            | (descartado — não é métrica de uso)  |

### Endpoints

- `GET /analytics/system` — visão global: contagens, aulas em andamento,
  uso diário (7d), top professores e salas
- `GET /analytics/teacher/{teacher_id}` — performance individual:
  total de aulas, minutos, breakdown de intents, última atividade
- `GET /analytics/class/{classroom_id}` — uso da sala/turma:
  sessões, minutos totais, professores únicos
- `GET /analytics/events?event_type=&teacher_id=&...` — query bruta
  com filtros (debug/inspeção)
- `POST /classroom/end-class` — encerra aula (publica `class_ended`
  pareando com `class_started` por `correlation_id`)

### Configuração

```env
ANALYTICS_BACKEND=sqlite
ANALYTICS_SQLITE_PATH=.analytics/events.db
```

### Limitações conhecidas

- `class_ended` é manual via endpoint. Auto-detecção (timeout, novo
  professor entrando) fica como TODO.
- Sem rotação/retenção do SQLite — para volume alto, adicionar política
  de purge ou particionamento por data.
- Métricas em Python; agregações pesadas (>milhões de eventos) vão
  precisar virar materialized views.
