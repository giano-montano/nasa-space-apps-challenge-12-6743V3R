/** Copiloto IA: panel lateral sencillo. Habla con POST /api/chat (Groq en el servidor). */
(() => {
  const $ = (id) => document.getElementById(id);
  const panel = $('chatPanel'), log = $('chatLog'), form = $('chatForm'), input = $('chatInput');
  if (!panel) return;
  const history = [];
  const SUGGESTIONS = ['¿Qué estoy viendo?', '¿Hay candidatos a asteroide en este campo?', 'Explícame el modo Diferencia'];

  const add = (role, text) => {
    const d = document.createElement('div');
    d.className = 'chat-msg ' + role;
    d.textContent = text;
    log.appendChild(d); log.scrollTop = log.scrollHeight;
    return d;
  };

  function context() {
    const a = window.app; if (!a) return {};
    const s = a.state, v = a.view || {}, det = v.detection || {};
    return {
      objeto: s.target, ra: s.ra, dec: s.dec, fov_arcmin: s.fov, modo: s.mode, detectores: s.detectors,
      epocas: (v.frames || []).map((f) => f.date).slice(0, 12),
      candidatos: (det.candidates || []).slice(0, 8),
    };
  }

  async function send(text) {
    text = text.trim(); if (!text) return;
    add('user', text); history.push({ role: 'user', content: text });
    input.value = '';
    const wait = add('bot', '…');
    try {
      const r = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: history, context: context() }) });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || 'Error');
      wait.textContent = j.reply; history.push({ role: 'assistant', content: j.reply });
    } catch (e) {
      wait.textContent = e.message || 'No pude responder ahora.'; wait.classList.add('err');
      history.pop();
    }
    log.scrollTop = log.scrollHeight;
  }

  const toggle = (open) => {
    panel.hidden = !(open ?? panel.hidden);
    $('btnChat').setAttribute('aria-expanded', String(!panel.hidden));
    if (!panel.hidden) input.focus();
  };

  add('bot', 'Hola, soy el Copiloto de Drift. Pregúntame sobre lo que ves en pantalla.');
  SUGGESTIONS.forEach((q) => {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'chat-pill'; b.textContent = q;
    b.addEventListener('click', () => send(q));
    $('chatSuggest').appendChild(b);
  });
  $('btnChat').addEventListener('click', () => toggle());
  $('chatClose').addEventListener('click', () => toggle(false));
  form.addEventListener('submit', (e) => { e.preventDefault(); send(input.value); });
  document.addEventListener('keydown', (e) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); toggle(true); } });

  // Sin servidor (frontend estático) el copiloto se oculta.
  fetch('/api/chat/status').then((r) => r.json()).then((j) => { if (!j.enabled) $('btnChat').hidden = true; })
    .catch(() => { $('btnChat').hidden = true; });
})();
