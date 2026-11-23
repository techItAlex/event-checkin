const resultBox = document.getElementById('result');
const manual = document.getElementById('manual');

// Debounce: ignore the same token for 2 seconds.
let lastToken = null, lastTime = 0;

function show(cls, html) {
  resultBox.className = 'result ' + cls;
  resultBox.innerHTML = html;
}
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function submitToken(token) {
  token = token.trim();
  if (!token) return;
  const t = Date.now();
  if (token === lastToken && t - lastTime < 2000) return;
  lastToken = token; lastTime = t;
  try {
    const res = await fetch('/api/checkin', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({token})
    });
    if (res.status === 401) { location.href = '/login?next=/checkin'; return; }
    const d = await res.json();
    if (d.status === 'ok') {
      show('ok', `✔ ${esc(d.name)}<small>${esc(d.organization)}</small>`);
    } else if (d.status === 'already') {
      show('already', `${esc(d.name)}<small>${esc(d.message)}</small>`);
    } else {
      show('invalid', '✖ Invalid ticket');
    }
  } catch (err) {
    show('invalid', 'Network error, try again');
  }
}

// USB scanner / manual input (always focused)
manual.addEventListener('keydown', e => {
  if (e.key === 'Enter') { submitToken(manual.value); manual.value = ''; }
});
document.addEventListener('click', e => {
  if (e.target.tagName !== 'BUTTON' && e.target.tagName !== 'A') manual.focus();
});
manual.addEventListener('blur', () => setTimeout(() => manual.focus(), 200));

// Camera scanner
if (window.Html5Qrcode) {
  const scanner = new Html5Qrcode('reader');
  scanner.start({facingMode: 'environment'}, {fps: 10, qrbox: 250},
    text => submitToken(text), () => {})
    .catch(() => {
      document.getElementById('reader').textContent =
        'Camera unavailable (needs HTTPS or localhost). Use the input box below.';
    });
}
