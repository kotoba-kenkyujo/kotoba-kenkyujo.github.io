// どのページでも使う仕組み：メニュー、明るい／暗い表示、リンクのコピー、ことばくじ、言葉の長さの図
(() => {
  const count = (path, title) => { if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path, title, event: true }); };

  // メニュー
  const menu = document.querySelector('.menu-btn');
  const nav = document.getElementById('nav');
  if (menu && nav) menu.addEventListener('click', () => menu.setAttribute('aria-expanded', nav.classList.toggle('open')));

  // 明るい表示と暗い表示（最初は端末の設定。選んだほうを覚える）
  document.querySelectorAll('.theme-btn').forEach(b => b.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('kotoba-theme', next); } catch (e) { /* 保存できない環境では、その場だけ切り替える */ }
    count('theme/' + next, '表示の切り替え：' + next);
  }));

  // リンクのコピー
  document.querySelectorAll('.share-btn.copy').forEach(b => b.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(b.dataset.url);
      const s = b.querySelector('span');
      const before = s.textContent;
      s.textContent = 'コピーしました';
      setTimeout(() => { s.textContent = before; }, 2000);
    } catch (e) { /* コピーできない環境では何もしない */ }
  }));

  // ことばくじ：ほかの会社のページへ
  const root = document.querySelector('.logo')?.getAttribute('href') || './';
  // トップの「ほかのことば」（.today-dice）は、その場で入れ替えるだけなので除く
  document.querySelectorAll('.dice:not(.today-dice)').forEach(b => b.addEventListener('click', async () => {
    try {
      const list = await (await fetch(root + 'pick.json')).json();
      const pool = list.filter(u => !location.pathname.endsWith(u));
      location.href = root + pool[Math.floor(Math.random() * pool.length)];
    } catch (e) { /* 読み込めないときは何もしない */ }
  }));

  // 言葉の長さの図：点を押すと、その言葉を出す（トップ）／一覧のその言葉に印を付ける（統計）
  const study = document.querySelector('.len-study');
  document.querySelectorAll('.strip').forEach(strip => {
    const pick = strip.parentElement.querySelector('.dot-pick');
    const dots = [...strip.querySelectorAll('.dot')];
    dots.forEach(d => d.addEventListener('click', () => {
      const on = d.getAttribute('aria-pressed') !== 'true';
      dots.forEach(x => x.setAttribute('aria-pressed', 'false'));
      d.setAttribute('aria-pressed', on);
      count('length-dot/' + d.dataset.id, '長さの図の点');
      if (pick) {
        pick.hidden = !on;
        if (on) {
          pick.innerHTML = '';
          const a = document.createElement('a');
          a.href = d.dataset.href;
          a.textContent = d.dataset.w;
          const s = document.createElement('small');
          s.textContent = d.dataset.co + '　' + d.dataset.len + '字';
          a.appendChild(s);
          pick.appendChild(a);
        }
      }
      if (study) {
        study.querySelectorAll('.len-list li').forEach(li => li.classList.toggle('hit', on && li.dataset.id === d.dataset.id));
        const hit = study.querySelector('.len-list li.hit');
        if (hit) { resetBins(); hit.scrollIntoView({ block: 'center', behavior: 'smooth' }); }
      }
    }));
  });

  // 統計：字数の幅で絞る・並べ替える
  let resetBins = () => {};
  if (study) {
    const list = study.querySelector('.len-list');
    const items = [...list.children];
    const bins = [...study.querySelectorAll('.len-bins button')];
    const dots = [...study.querySelectorAll('.dot')];
    const apply = (lo, hi, latin) => {
      items.forEach(li => {
        const n = +li.dataset.len;
        const show = latin ? li.dataset.latin === '1' : (li.dataset.latin !== '1' && (lo === null || (n >= lo && n <= hi)));
        li.hidden = !show;
      });
      dots.forEach(d => d.classList.toggle('dim', lo !== null && !(+d.dataset.len >= lo && +d.dataset.len <= hi)));
    };
    resetBins = () => { bins.forEach(x => x.setAttribute('aria-pressed', 'false')); apply(null, null, false); };
    bins.forEach(b => b.addEventListener('click', () => {
      const on = b.getAttribute('aria-pressed') !== 'true';
      bins.forEach(x => x.setAttribute('aria-pressed', 'false'));
      b.setAttribute('aria-pressed', on);
      if (!on) { apply(null, null, false); return; }
      if (b.dataset.latin) apply(-1, -1, true); else apply(+b.dataset.lo, +b.dataset.hi, false);
      count('length-bin/' + (b.dataset.latin ? 'latin' : b.dataset.lo), '長さの幅');
    }));
    study.querySelectorAll('.sorter button').forEach(b => b.addEventListener('click', () => {
      study.querySelectorAll('.sorter button').forEach(x => x.setAttribute('aria-pressed', 'false'));
      b.setAttribute('aria-pressed', 'true');
      const dir = b.dataset.sort === 'desc' ? -1 : 1;
      items.slice().sort((a, c) => dir * ((+a.dataset.len || 0) - (+c.dataset.len || 0))).forEach(li => list.appendChild(li));
    }));
  }
  // トップの収蔵の数：読み込みが終わってから0から数え上げる（コミュニティ図鑑と同じ作り。2026-11-09）
  // 待っているあいだは数字を隠し、桁が増えても横にずれないよう幅を先に取っておく。動きを減らす設定では何もしない
  const counters = [...document.querySelectorAll('[data-count]')].filter(el => parseInt(el.dataset.count, 10) > 0);
  if (counters.length && window.requestAnimationFrame && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    counters.forEach(el => { el.style.display = 'inline-block'; el.style.minWidth = el.dataset.count.length + 'ch'; el.style.opacity = '0'; });
    let started = false;
    const startCount = () => {
      if (started) return;
      started = true;
      let t0 = null;
      const step = t => {
        if (t0 === null) t0 = t;
        const p = Math.min(1, (t - t0) / 1000);
        const e = 1 - Math.pow(1 - p, 3);
        counters.forEach(el => { el.textContent = String(Math.round(parseInt(el.dataset.count, 10) * e)); });
        if (p < 1) requestAnimationFrame(step);
      };
      counters.forEach(el => { el.textContent = '0'; el.style.opacity = ''; });
      requestAnimationFrame(step);
    };
    const whenLoaded = new Promise(ok => { if (document.readyState === 'complete') ok(); else addEventListener('load', ok); });
    const whenFonts = document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve();
    Promise.all([whenLoaded, whenFonts]).then(() => requestAnimationFrame(() => requestAnimationFrame(startCount)));
    setTimeout(startCount, 2500);  // 読み込みに時間がかかっても、2.5秒たったら始める
  }
  // 会社のページ：読み進めたら下に前後の会社の帯を出し、ページ下の前後の帯が見えたら隠す（2026-11-09）
  const mini = document.querySelector('.mini-nav');
  const pagerEnd = document.querySelector('.pager');
  const firstScroll = document.querySelector('.scroll');
  if (mini && pagerEnd && firstScroll && 'IntersectionObserver' in window) {
    let pastTop = false, endSeen = false;
    const sync = () => { mini.hidden = !(pastTop && !endSeen); };
    new IntersectionObserver(es => { es.forEach(e => { pastTop = !e.isIntersecting && e.boundingClientRect.top < 0; }); sync(); }).observe(firstScroll);
    new IntersectionObserver(es => { es.forEach(e => { endSeen = e.isIntersecting; }); sync(); }).observe(pagerEnd);
  }
  const calm = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  // 会社のページ：掛け軸を上の軸から下へひらく（2026-11-15 見本の案1）。高さを測って --scroll-h に入れ、.rise を .unroll に替える
  const unroll = el => {
    const h = el.clientHeight;
    if (!h) return false;
    el.style.setProperty('--scroll-h', h + 'px');
    el.classList.remove('rise', 'unroll');
    void el.offsetWidth;
    el.classList.add('unroll');
    return true;
  };
  // 先読み（案12）で裏で開いたページは、表示されたときにひらく。ページをまたぐ動き（案9）で移ってきたときは、つながった掛け軸をひらかない
  const openScrolls = () => { if (!calm()) document.querySelectorAll('figure.scroll.rise').forEach(unroll); };
  if (document.prerendering) document.addEventListener('prerenderingchange', openScrolls, { once: true }); else openScrolls();
  // トップ：今日のことばのくじ（その場で、ほかの会社の北極星に入れ替える。2026-11-09）。
  // 2026-11-15 見本の案14：掛け軸を巻き上げてから、新しい言葉でひらく。英字が主の言葉は縦書きの入れ物ごと横書きに入れ替える（前は縦書きの中に入って横倒しになっていた）
  const todayBtn = document.querySelector('.today-dice');
  const poolEl = document.getElementById('today-pool');
  const todayEl = document.querySelector('.today');
  if (todayBtn && poolEl && todayEl) {
    let pool = [];
    try { pool = JSON.parse(poolEl.textContent); } catch (e) { /* くじが使えなくても今日のことばは出ている */ }
    let last = todayEl.getAttribute('href');
    let busy = null, pending = null;
    const render = p => {
      todayEl.setAttribute('href', p.url);
      todayEl.setAttribute('aria-label', '今日のことば　' + p.co);
      todayEl.classList.toggle('latin', p.latin);
      const old = todayEl.querySelector('.tate-wrap, .yoko');
      let block;
      if (p.latin) {
        block = document.createElement('p');
        block.className = 'yoko';
        block.innerHTML = p.html;
      } else {
        block = document.createElement('div');
        block.className = 'tate-wrap';
        const t = document.createElement('p');
        t.className = p.long ? 'tate long' : 'tate';
        t.innerHTML = p.html;
        block.appendChild(t);
      }
      old.replaceWith(block);
      todayEl.querySelector('.foot').innerHTML = p.seal + '<span class="who"></span>';
      todayEl.querySelector('.foot .who').textContent = p.co;
      todayEl.querySelector('.day').textContent = 'ことばくじ';
    };
    todayBtn.addEventListener('click', () => {
      const cands = pool.filter(p => p.url !== last);
      if (!cands.length) return;
      const p = cands[Math.floor(Math.random() * cands.length)];
      last = p.url;
      if (calm() || !todayEl.animate) { render(p); return; }
      pending = p;
      if (busy) return;  // 巻き上げの途中に押されたら、最後に引いた言葉でひらく
      const h = todayEl.clientHeight;
      const ease = 'cubic-bezier(.45, .05, .25, 1)';
      todayEl.classList.remove('rise', 'unroll');
      const opts = { duration: 520, easing: ease, fill: 'forwards' };
      busy = todayEl.animate([{ clipPath: 'inset(-40px -40px -40px -40px)' }, { clipPath: 'inset(-40px -40px calc(100% - 7px) -40px)' }], opts);
      let rod = null;
      try { rod = todayEl.animate([{ transform: 'none' }, { transform: 'translateY(' + (-h) + 'px)' }], Object.assign({ pseudoElement: '::after' }, opts)); } catch (e) { /* 軸だけ動かせないときは紙だけ巻き上げる */ }
      busy.finished.then(() => {
        render(pending);
        busy.cancel();
        if (rod) rod.cancel();
        busy = null;
        unroll(todayEl);
      });
    });
  }
  // 近いことば：横のレールを矢印で1枚ずつ送る。端では矢印を消す（2026-11-09）
  document.querySelectorAll('.near-rail-wrap').forEach(wrap => {
    const rail = wrap.querySelector('.near-rail');
    const prev = wrap.querySelector('.rail-btn.prev');
    const next = wrap.querySelector('.rail-btn.next');
    const step = () => { const card = rail.querySelector('.near-card'); return card ? card.getBoundingClientRect().width + 16 : 240; };
    const sync = () => { prev.disabled = rail.scrollLeft < 4; next.disabled = rail.scrollLeft + rail.clientWidth >= rail.scrollWidth - 4; };
    prev.addEventListener('click', () => rail.scrollBy({ left: -step() * 2, behavior: 'smooth' }));
    next.addEventListener('click', () => rail.scrollBy({ left: step() * 2, behavior: 'smooth' }));
    rail.addEventListener('scroll', sync, { passive: true });
    addEventListener('resize', sync);
    sync();
    // 位置の点（2026-11-15 見本の案11）：カードが6割以上見えていたら、その点を塗る。押すとそのカードへ
    const cards = [...rail.querySelectorAll('.near-card')];
    if (cards.length < 2 || !('IntersectionObserver' in window)) return;
    const box = document.createElement('div');
    box.className = 'rail-dots';
    box.setAttribute('role', 'group');
    box.setAttribute('aria-label', '近いことばの位置');
    const dots = cards.map((c, i) => {
      const d = document.createElement('button');
      d.type = 'button';
      d.setAttribute('aria-label', (i + 1) + '枚目（' + (c.querySelector('.who .nm') || c).textContent.trim() + '）へ');
      d.addEventListener('click', () => rail.scrollTo({ left: c.offsetLeft - 16, behavior: calm() ? 'auto' : 'smooth' }));
      box.appendChild(d);
      return d;
    });
    wrap.after(box);
    const io = new IntersectionObserver(es => es.forEach(e => dots[cards.indexOf(e.target)].classList.toggle('on', e.intersectionRatio >= 0.6)), { root: rail, threshold: [0, 0.6, 1] });
    cards.forEach(c => io.observe(c));
  });

  // 会社の一覧の五十音の札・統計の章の札（2026-11-15 見本の案10・案15）：ヘッダーの下に留めた札のうち、いま読んでいる区画の札を塗る。
  // 留めた札の下から画面の3割の線より上に頭が来ている区画のうち、いちばん下のもの。同じ高さに並ぶ章（統計の2列）はまとめて塗る
  ['.kana-jump', '.toc'].forEach(barSel => {
    const bar = document.querySelector(barSel);
    if (!bar) return;
    const links = [...bar.querySelectorAll('a[href^="#"]')];
    const secs = links.map(a => document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1))));
    if (!secs.length || secs.some(x => !x)) return;
    let last = '';
    const paint = () => {
      const edge = bar.getBoundingClientRect().bottom;
      const line = edge + (innerHeight - edge) * 0.3;
      const tops = secs.map(x => x.getBoundingClientRect().top);
      const above = tops.filter(t => t <= line);
      const cur = above.length ? Math.max(...above) : null;
      const on = links.map((a, i) => cur !== null && Math.abs(tops[i] - cur) < 4);
      const key = on.join();
      if (key === last) return;
      last = key;
      let first = null;
      links.forEach((a, i) => { if (on[i]) { a.setAttribute('aria-current', 'true'); if (!first) first = a; } else a.removeAttribute('aria-current'); });
      if (first && bar.scrollWidth > bar.clientWidth) bar.scrollTo({ left: Math.max(0, first.offsetLeft - (bar.clientWidth - first.offsetWidth) / 2), behavior: calm() ? 'auto' : 'smooth' });
    };
    let ticking = false;
    addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(() => { ticking = false; paint(); }); } }, { passive: true });
    addEventListener('resize', paint);
    paint();
  });

  // ページをまたぐ動き（2026-11-15 見本の案9）：トップの新収蔵の行・近いことばのカードを押すと、押した言葉が次のページの掛け軸へつながる。
  // 前後の会社へは左右に滑る。押した言葉の行き先は、次のページで照らし合わせるため sessionStorage に一時的に覚える
  const KEY = 'kotoba-vt';
  let swapEl = null;
  const remember = v => { try { sessionStorage.setItem(KEY, JSON.stringify(v)); } catch (e) { /* 覚えられなくても移動はできる */ } };
  document.addEventListener('click', e => {
    const a = e.target.closest('a');
    if (!a) return;
    if (a.matches('.index a, .near-card')) {
      swapEl = a.querySelector('.w, .q');
      remember({ word: (a.getAttribute('href').split('#')[1] || '') });
    } else if (a.matches('.pager a, .side, .mini-nav a')) {
      swapEl = null;
      remember({ dir: a.matches('.pager a:first-child, .side.prev, .mini-nav a:first-child') ? 'backwards' : 'forwards' });
    } else {
      swapEl = null;
      try { sessionStorage.removeItem(KEY); } catch (err) { /* なにもしない */ }
    }
  });
  addEventListener('pageswap', e => {
    if (!e.viewTransition) return;
    let v = {};
    try { v = JSON.parse(sessionStorage.getItem(KEY) || '{}'); } catch (err) { /* なにもしない */ }
    if (v.dir) e.viewTransition.types.add(v.dir);
    if (swapEl) {
      swapEl.style.viewTransitionName = 'word';
      e.viewTransition.finished.finally(() => { swapEl.style.viewTransitionName = ''; });
    }
  });
  addEventListener('pagereveal', e => {
    let v = null;
    try { v = JSON.parse(sessionStorage.getItem(KEY) || 'null'); sessionStorage.removeItem(KEY); } catch (err) { /* なにもしない */ }
    if (!e.viewTransition || !v) return;
    if (v.dir) e.viewTransition.types.add(v.dir);
    document.querySelectorAll('figure.scroll').forEach(f => f.classList.remove('rise', 'unroll'));  // 動きを二重にしない
    if (!v.hasOwnProperty('word')) return;
    const byId = v.word && document.getElementById(v.word);
    const target = byId && byId.matches('.scroll') ? byId : document.querySelector('figure.scroll');
    if (!target) return;
    target.classList.remove('rise', 'unroll');
    target.style.viewTransitionName = 'word';
    e.viewTransition.finished.finally(() => { target.style.viewTransitionName = ''; });
  });
})();
