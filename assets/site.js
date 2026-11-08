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
  document.querySelectorAll('.dice').forEach(b => b.addEventListener('click', async () => {
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
})();
