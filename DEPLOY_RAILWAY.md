# Deploy no Railway — passo a passo (piloto, 1 sala)

Tempo total: 15-20 minutos. Custo: $0 (free tier) + ~$1-3/mês de Anthropic.

---

## 1. Pré-requisitos

- Conta no GitHub
- Conta no Railway (https://railway.app — login com GitHub)
- Anthropic API key (https://console.anthropic.com — opcional, sistema funciona sem)

---

## 2. Sobe o código no GitHub

```bash
cd ped-smart-classroom

# Inicia git se ainda não tiver
git init
git add .
git commit -m "PED Smart Classroom — versão piloto"

# Cria repositório no GitHub (web ou CLI)
# Pelo CLI (gh): gh repo create ped-smart-classroom --private --source=. --push
# Ou pela web: cria o repo no github.com, depois:
git remote add origin git@github.com:SEU_USER/ped-smart-classroom.git
git push -u origin main
```

⚠️ **Garanta que `.env` está no `.gitignore`** — não suba secrets pro GitHub.

---

## 3. Cria projeto no Railway

1. https://railway.app → **New Project** → **Deploy from GitHub repo**
2. Seleciona o repo `ped-smart-classroom`
3. Railway detecta o `railway.json` e o `Procfile`, começa o build

O primeiro deploy demora ~2-3 min. Vai falhar porque ainda falta env vars.

---

## 4. Configura volume persistente

Sem isso, **toda redeploy apaga o SQLite e o memory_store.json**. Crítico.

1. No projeto Railway → **Settings** → **Volumes** → **Create**
2. Mount path: `/data`
3. Size: 1 GB (suficiente pra muitos meses)
4. Salvar e redeploy

---

## 5. Configura variáveis de ambiente

No projeto Railway → **Variables** → adiciona:

```
# Persistência (aponta pro volume)
ANALYTICS_SQLITE_PATH=/data/analytics/events.db
TELEMETRY_VOICE_PATH=/data/telemetry/voice.jsonl
MEMORY_PATH=/data/memory/memory_store.json
NUVEMPED_CACHE_PATH=/data/nuvemped.json

# Auth — gere uma string aleatória longa
API_KEY=cole-aqui-uma-string-aleatoria-de-32-caracteres

# CORS — depois de saber a URL final, restringir; por enquanto:
CORS_ORIGINS=*

# LLM (opcional)
VOICE_AI_API_KEY=sk-ant-sua-key-aqui
VOICE_AI_PROVIDER=anthropic
VOICE_AI_MODEL=claude-3-5-haiku-latest
VOICE_AI_MODE=auto
```

Como gerar uma `API_KEY` aleatória (terminal local):
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Salva → Railway redeploy automático.

---

## 6. Confere que subiu

Railway dá uma URL tipo `ped-smart-classroom-production.up.railway.app`.

```bash
# Health (público — sempre 200)
curl https://SEU_DOMINIO.up.railway.app/health

# Endpoint protegido — sem key, dá 401
curl -X POST https://SEU_DOMINIO.up.railway.app/voice/command \
  -H 'Content-Type: application/json' \
  -d '{"text":"próximo slide","teacher_id":"prof-01"}'
# Esperado: {"detail":"Missing or invalid X-API-Key header"}

# Com key, funciona
curl -X POST https://SEU_DOMINIO.up.railway.app/voice/command \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: SUA_API_KEY' \
  -d '{"text":"próximo slide","teacher_id":"prof-01"}'
# Esperado: 202, intent=next_slide
```

---

## 7. Acessa o frontend no tablet

No tablet (Chrome em fullscreen):

1. Abre `https://SEU_DOMINIO.up.railway.app/ui/`
2. **Frontend pede a API key** — abre console do Chrome (F12 → Console) e roda:
   ```javascript
   localStorage.setItem('PED_API_KEY', 'sua-api-key-aqui');
   location.reload();
   ```
3. Pronto. Todos os requests do frontend agora levam o header.

> **Tablet em modo kiosk:** Chrome → 3 pontos → **Adicionar à tela inicial** → marca "Abrir em janela separada". Vira app fullscreen.

---

## 8. USB-C → HDMI → Projetor

Conectar o cabo USB-C → HDMI no tablet espelha a tela pro projetor automaticamente.
Tablet vira display de comando (voz, presets); projetor mostra o mesmo conteúdo.

Se quiser que o tablet mostre algo diferente do projetor (ex: tablet=controles,
projetor=slide gigante), aí entra a história do **companion display** — tem
rascunho em `app/companion/DESIGN.md`.

---

## 9. Logs e debug

```
Railway → projeto → Deployments → último deploy → View Logs
```

O sistema loga muito. Útil:
- `[Analytics] SQLite pronto em /data/analytics/events.db` → volume funcionando
- `[VoiceAI] cid=... source=llm` → LLM respondendo
- `[VoiceAI] Sem API key; processor rodará apenas em modo offline` → faltou config

---

## 10. Quando precisar de mais

| Sintoma | Solução |
|---|---|
| LLM custando demais | Botão "usar LLM" no frontend deslige por default; ou `VOICE_AI_MODE=offline` |
| Volume cheio | Aumenta no Railway (paga por GB extra) ou implementa rotação |
| Free tier estourou | Railway cobra ~$5-10/mês após free tier |
| 2ª escola pedindo | Aí sim pensa em multi-tenant; me chame de novo |

---

## Checklist mínimo antes da 1ª aula real

- [ ] `/health` retorna 200
- [ ] `/voice/command` com API key responde corretamente
- [ ] Frontend abre em `/ui/` no tablet com `localStorage` configurado
- [ ] Microfone do tablet está funcionando (testar 🎙️)
- [ ] WiFi da sala estável
- [ ] Cabo USB-C → HDMI testado com o projetor da sala
- [ ] Volume `/data` confirmado (verifica logs após restart)
- [ ] Plano B: input de texto manual funciona se mic falhar
