// PED Smart Classroom — frontend
// Vanilla JS, sem dependências.

const API = window.location.origin;
const $ = (id) => document.getElementById(id);
const escapeHtml = (s) =>
    String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

// API key opcional — se o usuário rodou `localStorage.setItem('PED_API_KEY','...')`
// no console, todos os requests passam o header X-API-Key.
function authHeaders() {
    const h = { "Content-Type": "application/json" };
    try {
        const k = localStorage.getItem("PED_API_KEY");
        if (k) h["X-API-Key"] = k;
    } catch (e) { /* incognito ou bloqueado */ }
    return h;
}

// =====================================================================
// State central — fonte única de verdade pro contexto da sessão atual
// =====================================================================
const session = {
    teacher_id: null,
    teacher_name: null,
    classroom_id: null,
    correlation_id: null,    // do simulate-teacher; usado pra encerrar aula
    has_active_class: false,
    last_voice: null,        // último resultado de voz pra fluxo de correção
};

function setStatus(msg) { $("status").textContent = msg || ""; }

function setBusy(busy) {
    document.querySelectorAll("button").forEach(b => {
        if (b.id === "btn-end-class" && !session.has_active_class) return; // mantém disabled
        b.disabled = busy;
    });
    document.body.style.cursor = busy ? "wait" : "";
}

// =====================================================================
// Detecção de professor → simulate-teacher
// =====================================================================
async function detectTeacher() {
    const teacherId = $("teacher-id").value.trim();
    const teacherName = $("teacher-name").value.trim();
    const classroomId = $("classroom-id").value.trim() || "sala-display";
    const time = $("time").value;

    if (!teacherId || !teacherName) {
        setStatus("Informe ID e nome do professor.");
        return;
    }

    const body = {
        teacher_id: teacherId,
        teacher_name: teacherName,
        classroom_id: classroomId,
        confidence: 1.0,
    };
    if (time) body.simulated_time = `${time}:00`;

    setStatus("Consultando backend...");
    setBusy(true);

    try {
        const r = await fetch(`${API}/classroom/simulate-teacher`, {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify(body),
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();

        // Atualiza estado da sessão
        Object.assign(session, {
            teacher_id: teacherId,
            teacher_name: teacherName,
            classroom_id: classroomId,
            correlation_id: data.correlation_id || null,
            has_active_class: !!data.lesson,
        });
        $("btn-end-class").disabled = !session.has_active_class;

        render(teacherName, data);
        setStatus(`OK (${new Date().toLocaleTimeString()})${data.degraded ? " — DEGRADADO" : ""}`);
    } catch (err) {
        renderError(err.message);
        setStatus("Falha ao consultar.");
    } finally {
        setBusy(false);
    }
}

function render(teacherName, data) {
    const display = $("display");
    display.className = "display";

    if (data.lesson) {
        display.innerHTML = `
            <div class="info">
                <div class="row"><span class="label">Professor</span><span class="value">${escapeHtml(teacherName)}</span></div>
                <div class="row"><span class="label">Turma</span><span class="value">${escapeHtml(data.lesson.turma)}</span></div>
                <div class="row"><span class="label">Disciplina</span><span class="value">${escapeHtml(data.lesson.disciplina)}</span></div>
                <div class="row"><span class="label">Aula atual</span><span class="value">${escapeHtml(data.lesson.conteudo)}</span></div>
                <div class="row"><span class="label">Horário</span><span class="value">${escapeHtml(data.lesson.slot_start)} — ${escapeHtml(data.lesson.slot_end)}</span></div>
            </div>
        `;
    } else if (data.degraded) {
        display.classList.add("no-class");
        display.innerHTML = `
            <div class="info no-class">
                <div class="row"><span class="label">Professor detectado</span><span class="value">${escapeHtml(teacherName)}</span></div>
                <div class="warn">⚠ Modo degradado<br>${escapeHtml(data.warning || data.message)}</div>
            </div>
        `;
    } else {
        display.classList.add("no-class");
        display.innerHTML = `
            <div class="info no-class">
                <div class="row"><span class="label">Professor detectado</span><span class="value">${escapeHtml(teacherName)}</span></div>
                <div class="warn">${escapeHtml(data.message || "Sem aula agendada para este horário.")}</div>
            </div>
        `;
    }
}

function renderError(msg) {
    const display = $("display");
    display.className = "display";
    display.innerHTML = `<div class="error-msg">Erro: ${escapeHtml(msg)}<br>O backend está rodando?</div>`;
}

// =====================================================================
// Encerrar aula — end-class
// =====================================================================
async function endClass() {
    if (!session.correlation_id) {
        setStatus("Sem aula ativa pra encerrar.");
        return;
    }
    setBusy(true);
    try {
        const r = await fetch(`${API}/classroom/end-class`, {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({
                correlation_id: session.correlation_id,
                teacher_id: session.teacher_id,
                classroom_id: session.classroom_id,
                reason: "manual",
            }),
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        session.has_active_class = false;
        session.correlation_id = null;
        $("btn-end-class").disabled = true;
        setStatus(`Aula encerrada às ${new Date().toLocaleTimeString()}.`);
        $("display").className = "display idle";
        $("display").innerHTML = `<div class="idle-msg">Aula encerrada.</div>`;
    } catch (e) {
        setStatus(`Erro ao encerrar: ${e.message}`);
    } finally {
        setBusy(false);
    }
}

// =====================================================================
// Comando de voz — texto OU áudio (Web Speech API)
// =====================================================================
async function sendVoiceCommand(text) {
    const txt = (text ?? $("voice-text").value).trim();
    if (!txt) return;

    const useLLM = $("use-llm").checked;
    const endpoint = useLLM ? "/voice-ai/command" : "/voice/command";
    const payload = useLLM
        ? { audio_input: txt, classroom_id: session.classroom_id, teacher_id: session.teacher_id }
        : { text: txt,         classroom_id: session.classroom_id, teacher_id: session.teacher_id };

    showVoiceResult({ loading: true, text: txt });

    try {
        const r = await fetch(`${API}${endpoint}`, {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify(payload),
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        session.last_voice = { text: txt, ...data };
        showVoiceResult({ text: txt, ...data });
        // se telemetria está visível, atualiza
        if (!$("telemetry-panel").hidden) refreshTelemetry();
    } catch (e) {
        showVoiceResult({ text: txt, error: e.message });
    }
}

function showVoiceResult(r) {
    const bar = $("voice-result-bar");
    bar.hidden = false;
    bar.className = "voice-result-bar";

    if (r.loading) {
        bar.classList.add("loading");
        bar.innerHTML = `<span class="vr-text">"${escapeHtml(r.text)}"</span><span class="vr-status">aguardando...</span>`;
        return;
    }

    if (r.error) {
        bar.classList.add("error");
        bar.innerHTML = `<span class="vr-text">"${escapeHtml(r.text)}"</span><span class="vr-status">erro: ${escapeHtml(r.error)}</span>`;
        return;
    }

    const recognized = r.recognized ?? (r.intent != null);
    const sourceClass = `source-${r.source || (recognized ? "rules" : "none")}`;
    bar.classList.add(recognized ? "ok" : "warn", sourceClass);

    const ent = r.entities && Object.keys(r.entities).length
        ? ` ${escapeHtml(JSON.stringify(r.entities))}`
        : "";
    const sourceTag = r.source ? `<span class="vr-source">${escapeHtml(r.source)}</span>` : "";
    const intentText = recognized ? `${escapeHtml(r.intent)}${ent}` : "(unrecognized)";
    const correctBtn = `<button class="btn-correct" data-input="${escapeHtml(r.text)}" data-wrong="${escapeHtml(r.intent || '')}">Corrigir</button>`;

    bar.innerHTML = `
        <span class="vr-text">"${escapeHtml(r.text)}"</span>
        <span class="vr-arrow">→</span>
        <span class="vr-intent">${intentText}</span>
        ${sourceTag}
        ${correctBtn}
    `;
}

// =====================================================================
// Web Speech API — fallback gracioso se browser não suportar
// =====================================================================
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let isListening = false;

if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.lang = "pt-BR";
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onresult = (e) => {
        const transcript = e.results[0][0].transcript;
        $("voice-text").value = transcript;
        sendVoiceCommand(transcript);
    };
    recognition.onerror = (e) => {
        setStatus(`Mic erro: ${e.error}`);
        toggleMicVisual(false);
    };
    recognition.onend = () => toggleMicVisual(false);
} else {
    $("btn-mic").disabled = true;
    $("btn-mic").title = "Web Speech API não disponível neste browser (use Chrome/Edge)";
}

function toggleMicVisual(on) {
    isListening = on;
    $("btn-mic").classList.toggle("listening", on);
    $("btn-mic").textContent = on ? "🔴" : "🎙️";
}

function toggleMic() {
    if (!recognition) return;
    if (isListening) {
        recognition.stop();
    } else {
        try {
            recognition.start();
            toggleMicVisual(true);
        } catch (e) {
            setStatus(`Mic: ${e.message}`);
        }
    }
}

// =====================================================================
// Correção (memory) — modal pequeno
// =====================================================================
function openCorrectModal(input, wrong) {
    $("correct-input").textContent = input;
    $("correct-wrong").textContent = wrong || "(unrecognized)";
    $("correct-modal").showModal();
}

async function saveCorrect() {
    const input = $("correct-input").textContent;
    const wrong = $("correct-wrong").textContent;
    const correct = $("correct-intent").value;
    try {
        const r = await fetch(`${API}/memory/correct`, {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({
                input,
                correct_intent: correct,
                wrong_intent: wrong === "(unrecognized)" ? null : wrong,
                teacher_id: session.teacher_id,
            }),
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        $("correct-modal").close();
        setStatus(`Correção salva: "${input}" → ${correct}`);
    } catch (e) {
        setStatus(`Erro ao salvar: ${e.message}`);
    }
}

// =====================================================================
// Painel de telemetria
// =====================================================================
async function refreshTelemetry() {
    try {
        const [sumRes, recRes] = await Promise.all([
            fetch(`${API}/telemetry/voice/summary`),
            fetch(`${API}/telemetry/voice/recent?limit=10`),
        ]);
        const sum = await sumRes.json();
        const rec = await recRes.json();
        renderTelemetrySummary(sum);
        renderTelemetryList(rec.items || []);
    } catch (e) {
        $("telemetry-summary").innerHTML = `<em class="warn">Erro: ${escapeHtml(e.message)}</em>`;
    }
}

function renderTelemetrySummary(s) {
    const c = s.counts || {};
    const ag = s.by_agreement || {};
    const agTags = Object.entries(ag).slice(0, 5).map(
        ([k, v]) => `<span class="tag">${escapeHtml(k)}: ${v}</span>`
    ).join(" ");
    $("telemetry-summary").innerHTML = `
        <div class="t-stats">
            <span>Total: <b>${c.total ?? 0}</b></span>
            <span>LLM: <b>${c.by_source_llm ?? 0}</b></span>
            <span>Regras: <b>${c.by_source_rules ?? 0}</b></span>
            <span>Não rec.: <b>${c.unrecognized ?? 0}</b></span>
            <span>Lat. média: <b>${s.avg_latency_ms ?? 0}ms</b></span>
        </div>
        <div class="t-agreements">${agTags || '<em>nenhuma comparação ainda</em>'}</div>
    `;
}

function renderTelemetryList(items) {
    if (!items.length) {
        $("telemetry-list").innerHTML = `<li class="empty">nenhum comando ainda</li>`;
        return;
    }
    $("telemetry-list").innerHTML = items.slice().reverse().map(item => {
        const intent = item.intent || "(unrec.)";
        const source = item.source || "?";
        const transcript = item.transcript || "";
        const sh = item.shadow ? ` <span class="tag-sh">shadow:${escapeHtml(item.shadow.agreement)}</span>` : "";
        return `<li class="src-${escapeHtml(source)}">
            <div class="t-line1">"${escapeHtml(transcript)}"</div>
            <div class="t-line2">→ <b>${escapeHtml(intent)}</b> <span class="tag">${escapeHtml(source)}</span>${sh}</div>
        </li>`;
    }).join("");
}

let telemetryPollHandle = null;

function toggleTelemetryPanel(show) {
    $("telemetry-panel").hidden = !show;
    document.body.classList.toggle("with-panel", show);
    if (show) {
        refreshTelemetry();
        telemetryPollHandle = setInterval(refreshTelemetry, 5000);
    } else if (telemetryPollHandle) {
        clearInterval(telemetryPollHandle);
        telemetryPollHandle = null;
    }
}

// =====================================================================
// Wiring de eventos
// =====================================================================
$("btn-detect").addEventListener("click", detectTeacher);
$("btn-end-class").addEventListener("click", endClass);
$("btn-voice").addEventListener("click", () => sendVoiceCommand());
$("btn-mic").addEventListener("click", toggleMic);
$("btn-refresh-telemetry").addEventListener("click", refreshTelemetry);

["teacher-id", "teacher-name", "classroom-id"].forEach(id =>
    $(id).addEventListener("keydown", e => { if (e.key === "Enter") detectTeacher(); })
);
$("voice-text").addEventListener("keydown", e => { if (e.key === "Enter") sendVoiceCommand(); });

// Presets de detecção (incluindo data-room)
document.querySelectorAll('.presets[data-group="teachers"] button').forEach(btn => {
    btn.addEventListener("click", () => {
        $("teacher-id").value = btn.dataset.id || "";
        $("teacher-name").value = btn.dataset.name || "";
        $("classroom-id").value = btn.dataset.room || "sala-display";
        $("time").value = btn.dataset.time || "";
        detectTeacher();
    });
});

// Presets de voz
document.querySelectorAll('.presets[data-group="voice"] button').forEach(btn => {
    btn.addEventListener("click", () => {
        $("voice-text").value = btn.dataset.voice || "";
        sendVoiceCommand(btn.dataset.voice);
    });
});

// Botão de correção (delegação porque o botão é injetado dinamicamente)
$("voice-result-bar").addEventListener("click", e => {
    if (e.target.classList.contains("btn-correct")) {
        openCorrectModal(e.target.dataset.input, e.target.dataset.wrong);
    }
});

$("btn-correct-cancel").addEventListener("click", () => $("correct-modal").close());
$("btn-correct-save").addEventListener("click", saveCorrect);

$("show-telemetry").addEventListener("change", e => toggleTelemetryPanel(e.target.checked));
