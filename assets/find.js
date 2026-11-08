// ことばを探す：言葉の中の語と層で絞り込む。?q= で開ける
(() => {
  const q = document.getElementById('q');
  const list = document.getElementById('list');
  const items = [...list.children];
  const n = document.getElementById('n');
  const empty = document.getElementById('empty');
  const btns = [...document.querySelectorAll('#layers button')];
  const words = items.map(li => li.querySelector('.w'));
  const plain = words.map(w => w.textContent);
  const esc = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  let layer = '';
  const norm = s => s.normalize('NFKC').toLowerCase();

  function run() {
    const terms = norm(q.value).split(/\s+/).filter(Boolean);
    let shown = 0;
    items.forEach((li, i) => {
      const ok = (!layer || li.dataset.layer === layer) && terms.every(t => li.dataset.s.includes(t));
      li.hidden = !ok;
      if (ok) shown++;
      let h = esc(plain[i]);
      if (ok && terms.length) terms.forEach(t => { if (t && plain[i].includes(t)) h = h.split(esc(t)).join('<mark>' + esc(t) + '</mark>'); });
      words[i].innerHTML = h;
    });
    n.textContent = shown;
    empty.hidden = shown > 0;
    const url = new URL(location.href);
    if (q.value) url.searchParams.set('q', q.value); else url.searchParams.delete('q');
    history.replaceState(null, '', url);
  }
  btns.forEach(b => b.addEventListener('click', () => {
    const on = b.getAttribute('aria-pressed') !== 'true';
    btns.forEach(x => x.setAttribute('aria-pressed', 'false'));
    b.setAttribute('aria-pressed', on);
    layer = on ? b.dataset.layer : '';
    run();
  }));
  q.addEventListener('input', run);
  const p = new URLSearchParams(location.search).get('q');
  if (p) { q.value = p; run(); }
})();
