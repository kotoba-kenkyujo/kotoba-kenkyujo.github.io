// ことばを探す：言葉の中の語・社名（ひらがな・英字も）と層で絞り、新しい順・会社順・短い順に並べる。?q= で開ける。
// 言い換え表（config/synonyms.json）で同じ仲間の語も拾う。検索の例には見つかる数を添え、0件のときはほかの語と、知らせるリンクを出す（2026-11-09）
(() => {
  const q = document.getElementById('q');
  const list = document.getElementById('list');
  const items = [...list.children];
  const n = document.getElementById('n');
  const empty = document.getElementById('empty');
  const emptyEx = document.getElementById('empty-ex');
  const desc = document.getElementById('layer-desc');
  const btns = [...document.querySelectorAll('#layers button')];
  const sorts = [...document.querySelectorAll('#sort button')];
  const words = items.map(li => li.querySelector('.w'));
  const plain = words.map(w => w.textContent);
  const esc = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const norm = s => s.normalize('NFKC').toLowerCase();
  const syn = (window.KOTOBA_SYN || []).map(g => g.map(norm));
  const count = (path, title) => { if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path, title, event: true }); };
  let layer = '';
  let timer = null;
  let lastSent = '';

  // 1つの語を、言い換え表の仲間に広げる（「パーパス」で「存在意義」「志」も見つかる）
  const expand = t => { const g = syn.find(g => g.includes(t)); return g ? g : [t]; };
  const termsOf = s => norm(s).split(/\s+/).filter(Boolean).map(expand);
  const hit = (li, terms) => terms.every(alts => alts.some(t => li.dataset.s.includes(t)));

  function run() {
    const terms = termsOf(q.value);
    let shown = 0;
    items.forEach((li, i) => {
      const ok = (!layer || li.dataset.layer === layer) && hit(li, terms);
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
      if (term === lastSent) return;
      lastSent = term;
      count((shown ? 'search/' : 'search-zero/') + term, (shown ? '検索：' : '検索（0件）：') + term);
    }, 1500);
  }

  // 層の札：選んだ層の説明を件数の横に1行だけ出す
  btns.forEach(b => b.addEventListener('click', () => {
    const on = b.getAttribute('aria-pressed') !== 'true';
    btns.forEach(x => x.setAttribute('aria-pressed', 'false'));
    b.setAttribute('aria-pressed', on);
    layer = on ? b.dataset.layer : '';
    desc.hidden = !on;
    desc.textContent = on ? b.dataset.desc : '';
    run();
  }));

  // 並べ替え：新しい順・古い順（収蔵した順）・短い順・長い順（字数）
  const keys = { new: li => -li.dataset.no, old: li => +li.dataset.no, short: li => +li.dataset.len, long: li => -li.dataset.len };
  sorts.forEach(b => b.addEventListener('click', () => {
    sorts.forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    const k = keys[b.dataset.sort];
    items.slice().sort((a, c) => k(a) - k(c) || (+c.dataset.no) - (+a.dataset.no)).forEach(li => list.appendChild(li));
    count('words-sort/' + b.dataset.sort, '並べ替え');
  }));
  q.addEventListener('input', run);

  // 検索の例：よく使われる語から、読み込むたびに5つ（実際に検索された語は2つまで）。見つかる数を添える
  const ex = document.getElementById('ex');
  const pick = t => { q.value = t; run(); q.focus(); };
  const chip = t => {
    const c = items.filter(li => hit(li, termsOf(t))).length;
    if (!c) return null;
    const b = document.createElement('button');
    b.type = 'button';
    b.innerHTML = esc(t) + '<small>' + c + '</small>';
    b.addEventListener('click', () => pick(t));
    return b;
  };
  let pool = [];
  try {
    const data = JSON.parse(ex.dataset.ex);
    const shuffle = a => a.map(v => [Math.random(), v]).sort((x, y) => x[0] - y[0]).map(v => v[1]);
    pool = data.tokens;
    const picks = shuffle(data.searched).slice(0, 2);
    shuffle(data.tokens).forEach(t => { if (picks.length < 5 && !picks.includes(t)) picks.push(t); });
    picks.map(chip).filter(Boolean).forEach(b => ex.appendChild(b));
    ex.hidden = !ex.children.length;
  } catch (e) { /* 例が出せなくても検索はできる */ }

  // 0件のとき：ほかの語の候補（よく使われる語から3つ）
  new MutationObserver(() => {
    if (empty.hidden || emptyEx.children.length) return;
    const lead = document.createElement('span');
    lead.textContent = 'ほかの語で探す';
    emptyEx.appendChild(lead);
    pool.slice(0, 3).map(chip).filter(Boolean).forEach(b => emptyEx.appendChild(b));
  }).observe(empty, { attributes: true, attributeFilter: ['hidden'] });

  const p = new URLSearchParams(location.search).get('q');
  if (p) { q.value = p; run(); }
})();
