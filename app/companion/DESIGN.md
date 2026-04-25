# Companion Display — Rascunho

> **Status:** rascunho / não implementado.
> Objetivo deste doc: travar a forma de integração com o resto do sistema
> (eventos, contratos) **sem** decidir os detalhes que ainda estão em aberto.

---

## 1. Ideia em uma frase

Cada aluno tem um **tablet** (chamado aqui de *companion display*) que roda
conteúdo **em paralelo** com o que o professor projeta. Pode haver
**periféricos físicos** (Arduino/ESP) acoplados pra interação tátil:
botão de dúvida, RFID de presença, joystick de quiz, etc.

```
   ┌───────────────────────┐         ┌──────────────────┐
   │  Projetor (sala)      │         │   Tablet aluno   │
   │  ← controlado pelo    │  PED    │   ← companion    │
   │    professor (voz)    │ ◄────►  │   display        │
   └───────────────────────┘  bus    └──────────────────┘
              ▲                              ▲
              │                              │ sync de slides,
              │ classroom_engine             │ atividades, vídeo
              │                              │
              ▼                              ▼
                    event_bus existente
                              ▲
                              │
                  ┌───────────┴────────────┐
                  │   Arduino / ESP32      │
                  │   (botão de dúvida,    │
                  │    RFID, etc)          │
                  └────────────────────────┘
```

Conteúdo do tablet pode ser de 3 sabores (a escolher por contexto):

1. **Mirror** — exibe exatamente o que o projetor mostra (lousa digital privada).
2. **Companion** — algo complementar: vídeo enquanto o professor explica,
   exercício enquanto a turma debate, glossário, transcrição.
3. **Atividade** — o tablet vira interface da atividade ativa
   (`activity_opened` no bus → tablet mostra o exercício).

---

## 2. Decisões EM ABERTO (preciso pensar)

> Cada item tem opções e consequências, sem escolha feita.

### 2.1 Hardware do companion
- [ ] **Tablet por aluno** vs. **tablet compartilhado** (1 por par/grupo)?
- [ ] **OS:** Android (mais barato, app nativo ou PWA) ou iPad (interfaces melhores, custo)?
- [ ] **Modo kiosk** (uma só tela, sem sair do app) — provavelmente sim.

### 2.2 Como o tablet recebe conteúdo do servidor PED
- [ ] **WebSocket** (push em tempo real, ideal pra mirror/sync) — recomendado.
- [ ] **SSE** (Server-Sent Events) — mais simples que WS, só servidor → cliente.
- [ ] **Polling HTTP** — mais simples ainda, custo de latência.
- [ ] **MQTT** (com broker tipo mosquitto) — ótimo se Arduino também falar MQTT;
       unifica protocolo.

### 2.3 Identificação do aluno no tablet
- [ ] Login manual (PIN/QR) — simples mas chato.
- [ ] **RFID via Arduino** (cartão na chegada) — bonito; integra periférico.
- [ ] Face detection (já temos `vision/`) — alavanca o que existe.
- [ ] Sem identificação — tablet é "da posição X", não do aluno Y.

### 2.4 Periférico físico (Arduino/ESP)
- [ ] **Que microcontrolador?**
  - **ESP32 / ESP8266** — tem WiFi, fala HTTP/MQTT/WebSocket nativo.
    *Recomendado* — não depende de cabo USB.
  - **Arduino UNO + cabo USB serial** — mais barato, mas amarra a máquina.
  - **Arduino + módulo NRF24/LoRa** — radio mesh, exagero pra sala fechada.
- [ ] **Que comunicação com o servidor?**
  - HTTP POST `/companion/peripheral/event` (request/response)
  - MQTT publish em tópico `ped/sala-7/peripheral/<device_id>`
  - WebSocket bi-direcional (mesmo canal do tablet)
- [ ] **Que entradas?** botão (dúvida, presença), potenciômetro (quiz quantitativo),
  RFID, sensor de movimento, buzzer (saída), LED RGB (saída).
- [ ] **Que saídas?** professor pode disparar feedback no Arduino do aluno?
  (LED verde se respondeu certo, vibração, etc)

### 2.5 Sincronização de vídeo (caso 2 — companion)
- [ ] Vídeo **streaming** via servidor (precisa banda) OU **pré-baixado** no tablet
  (offline-first, mais robusto pra sala com WiFi ruim)?
- [ ] **Quem dispara o play?** Professor (via comando de voz `play_video`)
  ou tablet roda autonomamente quando entra em "modo companion"?
- [ ] **Sync de timestamp:** todos os tablets no mesmo segundo, ou cada um livre?
  (Se sync, vai precisar de relógio comum — NTP basta? Compensar latência?)

### 2.6 Offline / modo degradado
- [ ] Tablet funciona se cair a rede? Cacheia conteúdo localmente (PWA / service worker)?
- [ ] Arduino faz buffer de eventos e re-envia quando voltar?

---

## 3. Contrato com o sistema existente (essa parte fixo agora)

Independente das decisões acima, o **modo de conversa** com o resto do PED
já dá pra fixar. É só `event_bus`, padrão da casa.

### 3.1 Eventos novos a serem publicados pelo companion

Reservados em `events.py` deste módulo (ainda sem handler):

| Evento                      | Origem        | Payload mínimo                                    | Pra quê |
|-----------------------------|---------------|---------------------------------------------------|---------|
| `companion_connected`       | tablet        | device_id, classroom_id, student_id?              | analytics; mostra ícone "X tablets ativos" |
| `companion_disconnected`    | tablet        | device_id                                         | idem    |
| `companion_button_pressed`  | arduino       | device_id, button, classroom_id, student_id?     | dúvida do aluno → notifica professor |
| `companion_quiz_answered`   | tablet/arduino| device_id, question_id, answer, student_id       | atividade — alimenta o sistema de chamada/atividades |
| `companion_rfid_scanned`    | arduino       | device_id, tag_id, classroom_id                  | presença automática; bate com `mark_attendance` |

### 3.2 Eventos do PED que o companion CONSOME

Vai precisar de um subscriber/proxy que escuta o bus e empurra pros tablets:

- `class_started` → tablet sai de standby, mostra cabeçalho da aula
- `class_ended` → tablet volta pra standby
- `slide_changed` → tablet espelha o slide (se mode=mirror)
- `activity_opened` → tablet abre a atividade
- `voice_*` → opcional, mostrar no tablet "professor disse: ..." pra acessibilidade

### 3.3 Endpoints (stubs)

Reservados em `router.py` deste módulo, retornando 501 por enquanto:

- `POST /companion/peripheral/event` — Arduino/ESP HTTP-faz POST aqui (alternativa ao MQTT)
- `WS /companion/ws/{device_id}`     — canal bidirecional do tablet
- `GET /companion/devices`           — lista o que tá conectado (debug)

### 3.4 Onde mora cada coisa

```
app/companion/
├── DESIGN.md         ← este arquivo
├── events.py         ← nomes dos eventos novos (reservados)
├── models.py         ← dataclasses tentativos: Companion, Peripheral, ContentPacket
├── ports.py          ← Protocols: CompanionTransport, ArduinoBridge
├── router.py         ← endpoints stub (501)
└── __init__.py       ← vazio; módulo NÃO é montado em main.py ainda
```

Quando for implementar, segue exatamente o padrão dos outros módulos:
`factory.py` com singleton, `services/` com lógica, `transports/` com adapters
(WebSocketTransport, MQTTTransport, etc), todos satisfazendo os Protocols
de `ports.py`.

---

## 4. Riscos / coisas que vão doer

- **Estado do tablet** é problema novo: hoje o sistema é stateless por aluno.
  Quando começar a tracking (qual aluno tá em qual tablet, o que ele já viu),
  vai precisar de persistência por aluno. Cogitar SQLite separado ou
  reusar o do analytics.

- **Sala com 30 tablets** = 30 conexões WebSocket abertas + Arduino. Vai
  pressionar o uvicorn worker. Não é dramático, mas considerar broker MQTT
  externo se passar disso por sala × N salas.

- **Privacidade**: o tablet vai capturar interações por aluno
  (`student_id` no payload). LGPD se aplica. Decidir cedo o que é registrado
  e por quanto tempo.

- **Calibração de sync de vídeo** entre 30 tablets é não-trivial. Se o
  caminho for "cada um roda livre", problema pequeno. Se for "todos no
  mesmo frame", problema sério (precisa NTP, compensação de latência,
  buffer de jitter).

---

## 5. Próxima ação concreta (quando voltar a esse módulo)

Decidir as caixinhas de **2.1 (hardware)** e **2.2 (transport)** —
essas duas ditam tudo o resto. Sugestão minha sem compromisso:

> **ESP32 + MQTT + tablet Android com PWA** — é o caminho de menor atrito:
> ESP32 fala MQTT nativo, tablet pode subscrever no mesmo broker via WebSocket
> sobre MQTT, o servidor PED publica no broker em vez de manter 30 conexões.
> Mas é só uma sugestão; se você já tem afinidade com Arduino UNO, vale
> pensar.
