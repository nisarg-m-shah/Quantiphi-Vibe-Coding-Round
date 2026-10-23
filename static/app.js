const $ = (s) => document.querySelector(s);
const msgs = $('#messages'), input = $('#input'), toneSel = $('#tone');
const sendBtn = $('#send'), regenBtn = $('#regen'), list = $('#history');
let currentId = null, busy = false;

function setBubble(el, role, text) {
  if (role === 'assistant') el.innerHTML = DOMPurify.sanitize(marked.parse(text)); // sanitised markdown
  else el.textContent = text;
}

function addBubble(role, text) {
  const el = document.createElement('div');
  el.className = 'bubble ' + role;
  setBubble(el, role, text);
  msgs.appendChild(el);
  msgs.scrollTop = msgs.scrollHeight;
  return el;
}

function setBusy(v) {
  busy = v;
  sendBtn.disabled = v;
  regenBtn.disabled = v;
}

async function loadList() {
  const convs = await (await fetch('/api/conversations')).json();
  list.innerHTML = '';
  convs.forEach((c) => {
    const d = document.createElement('div');
    d.className = 'item' + (c.id === currentId ? ' active' : '');
    d.textContent = c.title;
    d.onclick = () => !busy && openConv(c.id);
    list.appendChild(d);
  });
}

async function openConv(id) {
  const res = await fetch('/api/conversations/' + id);
  if (!res.ok) return;
  const conv = await res.json();
  currentId = id;
  msgs.innerHTML = '';
  conv.messages.forEach((m) => addBubble(m.role, m.content));
  const last = conv.messages[conv.messages.length - 1];
  regenBtn.hidden = !(last && last.role === 'assistant');
  loadList();
}

// Reads the SSE stream and fills the bubble progressively. Returns true on success.
async function streamInto(url, body, bubble) {
  setBusy(true);
  let pending = '', shown = '';
  const timer = setInterval(() => {
    if (!pending) return;
    const n = Math.max(1, Math.ceil(pending.length / 60)); // 1 char per tick, speeds up only on a big backlog
    shown += pending.slice(0, n);
    pending = pending.slice(n);
    setBubble(bubble, 'assistant', shown);
    msgs.scrollTop = msgs.scrollHeight;
  }, 18);
  try {
    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!res.ok) {
      const e = await res.json().catch(() => ({}));
      throw new Error(typeof e.detail === 'string' ? e.detail : 'Invalid request');
    }
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split('\n\n');
      buf = parts.pop();
      for (const p of parts) {
        if (!p.startsWith('data: ')) continue;
        const ev = JSON.parse(p.slice(6));
        if (ev.error) throw new Error(ev.error);
        if (ev.token) pending += ev.token; // queue it; the timer types it out
      }
    }
    while (pending) await new Promise((r) => setTimeout(r, 30)); // let the typing finish
    return true;
  } catch (e) {
    pending = '';
    bubble.textContent = '⚠ ' + e.message;
    bubble.classList.add('error');
    return false;
  } finally {
    clearInterval(timer);
    setBusy(false);
  }
}

$('#form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text || busy) return;
  if (!currentId) {
    const r = await fetch('/api/conversations', { method: 'POST' });
    currentId = (await r.json()).id;
  }
  input.value = '';
  addBubble('user', text);
  const bubble = addBubble('assistant', '…');
  const ok = await streamInto(`/api/conversations/${currentId}/messages`, { content: text, tone: toneSel.value }, bubble);
  if (ok) regenBtn.hidden = false;
  loadList();
});

regenBtn.onclick = async () => {
  if (busy || !currentId) return;
  const bubbles = msgs.querySelectorAll('.bubble.assistant');
  const last = bubbles[bubbles.length - 1];
  last.classList.remove('error');
  last.textContent = '…';
  const ok = await streamInto(`/api/conversations/${currentId}/regenerate`, { tone: toneSel.value }, last);
  if (!ok) setTimeout(() => openConv(currentId), 2500); // old answer is still in the DB; restore it
};

input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('#form').requestSubmit(); }
});

$('#new').onclick = () => { if (busy) return; currentId = null; msgs.innerHTML = ''; regenBtn.hidden = true; loadList(); };

loadList();