// ことばを探す：言葉の中の語・社名（ひらがな・英字も）と層で絞る。?q= で開ける。言い換え表（config/synonyms.json）で同じ仲間の語も拾う
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
  const norm = s => s.normalize('NFKC').toLowerCase();
  const syn = (window.KOTOBA_SYN || []).map(g => g.map(norm));
  let layer = '';
  let timer = null;
  let lastSent = '';

  // 1つの語を、言い換え表の仲間に広げる（「パーパス」で「存在意義」「志」も見つかる）
  const expand = t => { const g = syn.find(g => g.includes(t)); return g ? g : [t]; };

  function run() {
    const terms = norm(q.value).split(/\s+/).filter(Boolean).map(expand);
    let shown = 0;
    items.forEach((li, i) => {
      const ok = (!layer || li.dataset.layer === layer) && terms.every(alts => alts.some(t => li.dataset.s.includes(t)));
      li.hidden = !ok;
      if (ok) shown++;
      let h = esc(plain[i]);
      if (ok) terms.flat().forEach(t => { if (t && plain[i].includes(t)) h = h.split(esc(t)).join('<mark>' + esc(t) + '</mark>'); });
      words[i].innerHTML = h;
    });
    n.textContent = shown;
    empty.hidden = shown > 0;
    const url = new URL(location.href);
    if (q.value) url.searchParams.set('q', q.value); else url.searchParams.delete('q');
    history.replaceState(null, '', url);
    // 検索された語を数える（入力が1.5秒止まったとき。辞典・図鑑と同じ）
    clearTimeout(timer);
    const term = q.value.trim();
    if (term && term.length <= 20) timer = setTimeout(() => {
      if (term === lastSent || !window.goatcounter || !window.goatcounter.count) return;
      lastSent = term;
      window.goatcounter.count({ path: (shown ? 'search/' : 'search-zero/') + term, title: (shown ? '検索：' : '検索（0件）：') + term, event: true });
    }, 1500);
  }
  btns.forEach(b => b.addEventListener('click', () => {
    const on = b.getAttribute('aria-pressed') !== 'true';
    btns.forEach(x => x.setAttribute('aria-pressed', 'false'));
    b.setAttribute('aria-pressed', on);
    layer = on ? b.dataset.layer : '';
    run();
  }));
  q.addEventListener('input', run);

  // 検索の例：よく使われる語から、読み込むたびに5つ（実際に検索された語は2つまで）
  const ex = document.getElementById('ex');
  try {
    const data = JSON.parse(ex.dataset.ex);
    const shuffle = a => a.map(v => [Math.random(), v]).sort((x, y) => x[0] - y[0]).map(v => v[1]);
    const picks = shuffle(data.searched).slice(0, 2);
    shuffle(data.tokens).forEach(t => { if (picks.length < 5 && !picks.includes(t)) picks.push(t); });
    picks.forEach(t => {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = t;
      b.addEventListener('click', () => { q.value = t; run(); });
      ex.appendChild(b);
    });
    ex.hidden = picks.length === 0;
  } catch (e) { /* 例が出せなくても検索はできる */ }

  const p = new URLSearchParams(location.search).get('q');
  if (p) { q.value = p; run(); }
})();
