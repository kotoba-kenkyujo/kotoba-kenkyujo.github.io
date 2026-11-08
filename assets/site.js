// どのページでも使う仕組み：メニューの開閉、共有、ことばくじ
(() => {
  const menu = document.querySelector('.menu-btn');
  const nav = document.getElementById('nav');
  if (menu && nav) {
    menu.addEventListener('click', () => {
      const open = nav.classList.toggle('open');
      menu.setAttribute('aria-expanded', open);
    });
  }
  const root = document.querySelector('.logo')?.getAttribute('href') || './';
  document.querySelectorAll('.share').forEach(b => b.addEventListener('click', async () => {
    const data = { title: document.title, url: location.href.split('#')[0] };
    try {
      if (navigator.share) { await navigator.share(data); return; }
      await navigator.clipboard.writeText(data.url);
      b.setAttribute('aria-label', 'URLをコピーしました');
      b.textContent = '✓';
    } catch (e) { /* 共有を閉じたときは何もしない */ }
  }));
  document.querySelectorAll('.dice').forEach(b => b.addEventListener('click', async () => {
    try {
      const list = await (await fetch(root + 'pick.json')).json();
      const here = location.pathname;
      const pool = list.filter(u => !here.endsWith(u));
      location.href = root + pool[Math.floor(Math.random() * pool.length)];
    } catch (e) { /* 読み込めないときは何もしない */ }
  }));
})();
