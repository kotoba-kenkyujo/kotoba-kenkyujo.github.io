// ことばを探す：言葉の中の語・社名（ひらがな・英字も）と層で絞り、新しい順・古い順・短い順・長い順に並べる。?q= で開ける。
// 言い換え表（config/synonyms.json）で同じ仲間の語も拾う。検索の例には見つかる数を添え、0件のときはほかの語と、知らせるリンクを出す（2026-11-09）
// 2026-11-15 見本で採用：層の札の数を今の検索に合わせ、0件の札は押せなくする／0件のときは条件を1つ外したときの数をボタンで出す（案7）／
// 社名や読みに当たる会社の札を一覧の先頭に3社まで出す（案8）／言葉の文節の区切りと約物の詰め（build.py が作る HTML）を検索しても消さない
(() => {
  const q = document.getElementById('q');
  const list = document.getElementById('list');
  const items = [...list.children];
  const n = document.getElementById('n');
  const empty = document.getElementById('empty');
  const emptyEx = document.getElementById('empty-ex');
  const relax = document.getElementById('relax');
  const desc = document.getElementById('layer-desc');
  const cosBox = document.getElementById('co-cards');
  const btns = [...document.querySelectorAll('#layers button')];
  const sorts = [...document.querySelectorAll('#sort button')];
  const words = items.map(li => li.querySelector('.w'));
  const plain = words.map(w => w.textContent);
  const orig = words.map(w => w.innerHTML);
  const esc = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const reEsc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const norm = s => s.normalize('NFKC').toLowerCase();
  const syn = (window.KOTOBA_SYN || []).map(g => g.map(norm));
  const count = (path, title) => { if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path, title, event: true }); };
  const LABEL = Object.fromEntries(btns.map(b => [b.dataset.layer, b.firstChild.textContent]));
  let cos = [];
  try { cos = JSON.parse(document.getElementById('co-data').textContent); } catch (e) { /* 会社の札が出せなくても検索はできる */ }
  let layer = '';
  let timer = null;
  let lastSent = '';
  let lastIds = '';

  // 1つの語を、言い換え表の仲間に広げる（「パーパス」で「存在意義」「志」も見つかる）
  const expand = t => { const g = syn.find(g => g.includes(t)); return g ? g : [t]; };
  const termsOf = s => norm(s).split(/\s+/).filter(Boolean).map(expand);
  const hit = (li, terms) => terms.every(alts => alts.some(t => li.dataset.s.includes(t)));
  // 印（mark）：文節の <wbr> をまたいでも付ける。元の HTML（約物の詰め）はそのまま
  const markHtml = (html, text, ts) => {
    ts.forEach(t => {
      if (!t || !text.includes(t)) return;
      const pat = new RegExp([...t].map(c => reEsc(esc(c))).join('(?:<wbr>)?'), 'g');
      html = html.replace(pat, m => '<mark>' + m + '</mark>');
    });
    return html;
  };

  function run() {
    const terms = termsOf(q.value);
    const flat = terms.flat();
    let shown = 0, total = 0;
    const per = {};
    items.forEach((li, i) => {
      const m = hit(li, terms);
      if (m) { per[li.dataset.layer] = (per[li.dataset.layer] || 0) + 1; total++; }
      const ok = m && (!layer || li.dataset.layer === layer);
      li.hidden = !ok;
      if (ok) shown++;
      words[i].innerHTML = ok && flat.length ? markHtml(orig[i], plain[i], flat) : orig[i];
    });
    n.textContent = shown;
    // 層の札の数を、いまの検索に合わせる。0件の札は押せなくする（選んでいる札は外せるように残す）
    btns.forEach(b => {
      const c = per[b.dataset.layer] || 0;
      const s = b.querySelector('small');
      if (s.textContent !== String(c)) { s.textContent = c; s.classList.remove('tick'); void s.offsetWidth; s.classList.add('tick'); }
      if (!c && b.getAttribute('aria-pressed') !== 'true') b.setAttribute('aria-disabled', 'true'); else b.removeAttribute('aria-disabled');
    });
    // 会社の札：略した社名と読みだけを見る（「株式会社」で全社が当たらないように）
    const raw = norm(q.value).split(/\s+/).filter(Boolean);
    const found = raw.length ? cos.filter(c => { const hay = norm(c.short + ' ' + c.r); return raw.every(t => hay.includes(t)); }) : [];
    const rank = c => { const s = norm(c.short), r = norm(c.r), t = raw[0]; return (s === t || r === t) ? 0 : (s.startsWith(t) || r.startsWith(t)) ? 1 : 2; };
    found.sort((a, b) => rank(a) - rank(b) || a.r.localeCompare(b.r, 'ja'));
    const top = found.slice(0, 3);
    cosBox.innerHTML = '';
    top.forEach(c => {
      const a = document.createElement('a');
      a.className = 'co-card';
      a.href = '../c/' + c.id + '/';
      a.dataset.goatcounterClick = 'search-co/' + c.id;
      a.innerHTML = '<span class="cc-head"><span class="cc-nm">' + markHtml(esc(c.name), c.name, raw) + '</span><span class="cc-n"><b>' + c.n + '</b>語</span></span>' +
        '<span class="cc-body"><span class="cc-w">' + c.wh + '</span>' + c.seal + '</span><span class="cc-go">会社のページへ →</span>';
      cosBox.appendChild(a);
    });
    if (found.length > 3) {
      const more = document.createElement('p');
      more.className = 'cc-more';
      more.innerHTML = 'ほか<b>' + (found.length - 3) + '</b>社';
      cosBox.appendChild(more);
    }
    cosBox.hidden = !top.length;
    const ids = top.map(c => c.id).join(',');
    if (ids !== lastIds) { lastIds = ids; cosBox.classList.remove('in'); void cosBox.offsetWidth; cosBox.classList.add('in'); }
    // 0件のとき：条件を1つ外すと何語になるか。外せる条件がなければ、ほかの語の候補
    empty.hidden = shown > 0 || top.length > 0;
    relax.innerHTML = '';
    const opts = [];
    if (shown === 0) {
      if (layer && total) opts.push({ html: esc(LABEL[layer]) + 'を外すと<b>' + total + '</b>語', act: () => setLayer(null, false) });
      const words1 = q.value.trim().split(/\s+/).filter(Boolean);
      if (words1.length > 1) words1.forEach((t, k) => {
        const rest = words1.filter((_, j) => j !== k);
        const rt = termsOf(rest.join(' '));
        const c = items.filter(li => (!layer || li.dataset.layer === layer) && hit(li, rt)).length;
        if (c) opts.push({ html: '「' + esc(t) + '」を外すと<b>' + c + '</b>語', act: () => { q.value = rest.join(' '); } });
      });
      opts.forEach(o => {
        const b = document.createElement('button');
        b.type = 'button';
        b.innerHTML = o.html;
        b.addEventListener('click', () => { o.act(); run(); q.focus(); });
        relax.appendChild(b);
      });
      if (!opts.length && !emptyEx.children.length) fillEx();
    }
    relax.hidden = !opts.length;
    emptyEx.hidden = opts.length > 0;
    const url = new URL(location.href);
    if (q.value) url.searchParams.set('q', q.value); else url.searchParams.delete('q');
    history.replaceState(null, '', url);
    // 検索された語を数える（入力が1.5秒止まったとき。辞典・図鑑と同じ）
    clearTimeout(timer);
    const term = q.value.trim();
    if (term && term.length <= 20) timer = setTimeout(() => {
      if (term === lastSent) return;
      lastSent = term;
      count((shown || top.length ? 'search/' : 'search-zero/') + term, (shown || top.length ? '検索：' : '検索（0件）：') + term);
    }, 1500);
  }

  // 層の札：選んだ層の説明を件数の横に1行だけ出す
  const setLayer = (b, on) => {
    btns.forEach(x => x.setAttribute('aria-pressed', 'false'));
    if (b) b.setAttribute('aria-pressed', String(on));
    layer = on && b ? b.dataset.layer : '';
    desc.hidden = !layer;
    desc.textContent = layer ? b.dataset.desc : '';
  };
  btns.forEach(b => b.addEventListener('click', () => {
    if (b.getAttribute('aria-disabled') === 'true') return;
    setLayer(b, b.getAttribute('aria-pressed') !== 'true');
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

  // 0件で外せる条件がないとき：ほかの語の候補（よく使われる語から3つ）
  function fillEx() {
    const lead = document.createElement('span');
    lead.textContent = 'ほかの語で探す';
    emptyEx.appendChild(lead);
    pool.slice(0, 3).map(chip).filter(Boolean).forEach(b => emptyEx.appendChild(b));
  }

  const p = new URLSearchParams(location.search).get('q');
  if (p) { q.value = p; run(); }
})();
