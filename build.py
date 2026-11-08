"""会社のことば研究所のサイトを作る。Python の標準ライブラリだけで動く。

使い方:
  python3 build.py                      # config/site.json の CSV の URL から読む（空なら data/ の写し）
  python3 build.py --words testdata/words.csv --companies testdata/companies.csv   # 手元のCSVで試す
出力は _site/。手元のCSVで試したときは data/ を書き換えない。
"""
import csv, datetime, html, io, json, os, re, shutil, sys, unicodedata, urllib.parse, urllib.request
from collections import Counter, defaultdict, OrderedDict

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "_site")
JST = datetime.timezone(datetime.timedelta(hours=9))
NOW = datetime.datetime.now(JST)
TODAY = NOW.date()
esc = html.escape
CFG = json.load(open(os.path.join(ROOT, "config", "site.json"), encoding="utf-8"))
BASE = CFG["base_url"].rstrip("/") + "/"
VER = NOW.strftime("%Y%m%d%H%M")

WORD_COLS = ["ID", "会社ID", "会社名", "対象", "層", "会社での呼び名", "項目の順番", "言葉", "英語版", "使い始め", "使い終わり", "前の言葉のID", "出典URL", "出典の種類", "出典の日付", "確認日"]
COMPANY_COLS = ["ID", "会社名", "読み", "証券コード", "EDINETコード", "業種", "上場区分", "設立年", "公式サイト", "理念ページのURL"]
LAYERS = ["いちばん上", "目指す姿", "価値観"]


# ---------- 読み込み ----------
def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "kotoba-kenkyujo-build"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read().decode("utf-8")
    if body.lstrip().startswith("<"):
        raise SystemExit(f"CSVではなくHTMLが返ってきた: {url}")
    return body


def read_rows(text, cols):
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return []
    head = [h.strip() for h in rows[0]]
    idx = {c: head.index(c) for c in cols if c in head}
    out = []
    for r in rows[1:]:
        d = {c: (r[idx[c]].strip() if c in idx and idx[c] < len(r) else "") for c in cols}
        if d["ID"]:
            out.append(d)
    return out


def load():
    args = sys.argv[1:]
    local = "--words" in args
    if local:
        wtext = open(args[args.index("--words") + 1], encoding="utf-8").read()
        ctext = open(args[args.index("--companies") + 1], encoding="utf-8").read()
    else:
        wurl, curl = CFG.get("words_csv_url"), CFG.get("companies_csv_url")
        if wurl and curl:
            wtext, ctext = fetch(wurl), fetch(curl)
        else:
            print("CSVのURLが設定されていないので data/ の写しで作る")
            wtext = open(os.path.join(ROOT, "data", "words.csv"), encoding="utf-8").read()
            ctext = open(os.path.join(ROOT, "data", "companies.csv"), encoding="utf-8").read()
    words, comps = read_rows(wtext, WORD_COLS), read_rows(ctext, COMPANY_COLS)
    if not words:
        raise SystemExit("言葉が0件。公開を止める")
    if not local and CFG.get("words_csv_url"):
        old = os.path.join(ROOT, "data", "words.csv")
        if os.path.exists(old):
            n_old = len(read_rows(open(old, encoding="utf-8").read(), WORD_COLS))
            if n_old and len(words) < n_old * 0.5 and os.environ.get("ALLOW_SHRINK") != "1":
                raise SystemExit(f"言葉が {n_old} 件から {len(words)} 件に減った。公開を止める（意図どおりなら ALLOW_SHRINK=1）")
        os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
        open(os.path.join(ROOT, "data", "words.csv"), "w", encoding="utf-8").write(wtext)
        open(os.path.join(ROOT, "data", "companies.csv"), "w", encoding="utf-8").write(ctext)
    return words, comps


# ---------- データを整える ----------
def short_name(name):
    s = re.sub(r"^(株式会社|有限会社|合同会社)\s*|\s*(株式会社|有限会社|合同会社)$", "", name)
    return s or name


def pdate(s):
    for f in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s, f).date()
        except Exception:
            pass
    return None


def ym(s):
    m = re.match(r"(\d{4})/(\d{1,2})", s or "")
    return f"{m.group(1)}.{int(m.group(2))}" if m else ""


def dot(d):
    return f"{d.year}.{d.month}.{d.day}" if d else ""


KANJI_NUM = "〇一二三四五六七八九"


def kanji_date(d):
    def num(n):
        return "".join(KANJI_NUM[int(c)] for c in str(n))
    def small(n):
        if n < 10:
            return KANJI_NUM[n]
        return ("" if n // 10 == 1 else KANJI_NUM[n // 10]) + "十" + (KANJI_NUM[n % 10] if n % 10 else "")
    return f"{num(d.year)}年{small(d.month)}月{small(d.day)}日"


STOP = {"当社", "弊社", "我等", "我々", "私達", "以下", "全て", "一人", "一人ひとり", "目指", "通じ", "提供", "実現"}


def tokens(text):
    """言葉から数える語を取り出す。漢字の2〜4字の並び、カタカナの3字以上、英字の4字以上。"""
    t = unicodedata.normalize("NFKC", text)
    out = set()
    for m in re.findall(r"[一-龥々〆ヵヶ]{2,}", t):
        if len(m) <= 4:
            out.add(m)
        else:  # 長い漢字の並びは2字ずつに分ける（「人間生活産業」→「人間」「生活」「産業」）
            for i in range(0, len(m) - 1, 2):
                out.add(m[i:i + 2])
    out.update(m for m in re.findall(r"[ァ-ヴー]{3,}", t) if not set(m) <= {"ー"})
    out.update(m.lower() for m in re.findall(r"[A-Za-z]{4,}", t))
    return {x for x in out if x not in STOP}


def model(words, comps):
    C = OrderedDict()
    for c in sorted(comps, key=lambda c: c["ID"]):
        C[c["ID"]] = dict(c, short=short_name(c["会社名"]), words=[])
    for w in words:
        if w["会社ID"] not in C:
            C[w["会社ID"]] = {"ID": w["会社ID"], "会社名": w["会社名"], "short": short_name(w["会社名"]), "words": []}
            for k in COMPANY_COLS[2:]:
                C[w["会社ID"]][k] = ""
    prev_ids = {w["前の言葉のID"] for w in words if w["前の言葉のID"]}
    for w in words:
        w["old"] = bool(w["使い終わり"]) or w["ID"] in prev_ids
        w["no"] = int(re.sub(r"\D", "", w["ID"]) or 0)
        w["order"] = int(w["項目の順番"]) if w["項目の順番"].isdigit() else 0
        w["checked"] = pdate(w["確認日"])
        w["tokens"] = tokens(w["言葉"])
        w["co"] = C[w["会社ID"]]
        C[w["会社ID"]]["words"].append(w)
    C = OrderedDict((k, v) for k, v in C.items() if v["words"])
    for c in C.values():
        c["words"].sort(key=lambda w: (LAYERS.index(w["層"]) if w["層"] in LAYERS else 9, w["order"], w["no"]))
        c["url"] = f"c/{c['ID']}/"
        c["checked"] = max((w["checked"] for w in c["words"] if w["checked"]), default=None)
        srcs = []
        for w in c["words"]:
            if w["出典URL"] and w["出典URL"] not in srcs:
                srcs.append(w["出典URL"])
        c["srcs"] = srcs
        c["tokens"] = set().union(*(w["tokens"] for w in c["words"] if not w["old"]))
    return C


def src_label(w):
    m = re.search(r"\?(S[0-9A-Z]{7})$", w["出典URL"])
    kind = w["出典の種類"] or "出典"
    date = w["出典の日付"]
    d = pdate(date)
    when = f"{d.year}年{d.month}月{d.day}日提出" if d and kind == "有価証券報告書" else (f"{d.year}年{d.month}月{d.day}日" if d else "")
    tail = f"（EDINET {m.group(1)}）" if m else ""
    return " ".join(x for x in [kind, when] if x) + tail


# ---------- ページの枠 ----------
NAV = [("words/", "ことばを探す"), ("topics/", "研究テーマ"), ("history/", "言語史"), ("notes/", "研究ノート"), ("about/", "この研究所について")]


def page(path, title, body, desc=None, current=None, notes_exist=True, extra_head=""):
    depth = path.count("/")
    rel = "../" * depth
    full_title = f"{title}｜{CFG['name']}" if title != CFG["name"] else f"{CFG['name']}｜{CFG['subtitle']}"
    desc = desc or CFG["description"]
    canon = BASE + path
    cur_attr = ' aria-current="page"'
    nav = "".join(
        f'<a href="{rel}{u}"{cur_attr if current == u else ""}>{esc(t)}</a>'
        for u, t in NAV if notes_exist or u != "notes/"
    )
    gc = CFG.get("goatcounter")
    gc_tag = f'<script data-goatcounter="https://{esc(gc)}.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>' if gc else ""
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canon)}">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(canon)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(CFG['name'])}">
<meta name="twitter:card" content="summary">
<link rel="icon" href="{rel}assets/icon.svg" type="image/svg+xml">
<link rel="icon" href="{rel}assets/favicon-32.png" sizes="32x32">
<link rel="apple-touch-icon" href="{rel}assets/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Shippori+Mincho+B1:wght@500;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{rel}assets/style.css?v={VER}">
{extra_head}{gc_tag}
</head>
<body>
<a class="skip" href="#main">本文へ</a>
<header class="site-header"><div class="wrap header-inner">
  <a class="logo" href="{rel or './'}"><img src="{rel}assets/icon.svg" alt="" width="26" height="26">{esc(CFG['name'])}</a>
  <nav class="nav" id="nav" aria-label="サイト内">{nav}</nav>
  <a class="icon-btn" href="{rel}words/" aria-label="ことばを探す"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg></a>
  <button class="icon-btn menu-btn" type="button" aria-controls="nav" aria-expanded="false" aria-label="メニュー"><svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button>
</div></header>
<main id="main" class="wrap">
{body}
</main>
<footer class="footer"><div class="wrap">
  <div class="name"><img src="{rel}assets/icon.svg" alt="" width="24" height="24">{esc(CFG['name'])}</div>
  <nav aria-label="フッター">{nav}</nav>
  <small>運営　<a href="{esc(CFG['operator_url'])}" rel="noopener" target="_blank">{esc(CFG['operator'])}</a></small>
</div></footer>
<script src="{rel}assets/site.js?v={VER}" defer></script>
</body>
</html>
"""


def write(path, content):
    full = os.path.join(OUT, path, "index.html") if path.endswith("/") or path == "" else os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, "w", encoding="utf-8").write(content)


def seal(text):
    """落款。呼び名を縦書きで、2字ずつの列にして押す（長い呼び名は列が増える）"""
    t = re.sub(r"[（(].*?[）)]", "", text)
    if re.fullmatch(r"[\x00-\x7f]+", t):
        return f'<span class="seal latin">{esc(t)}</span>'
    return f'<span class="seal">{esc(t)}</span>'


def mostly_latin(text):
    letters = [ch for ch in text if not ch.isspace()]
    return bool(letters) and sum(1 for ch in letters if ord(ch) < 0x3000) / len(letters) > 0.5


def tate_class(text):
    return "tate long" if len(text) > 40 else "tate"


# ---------- トップ ----------
def build_top(C, W, stats, notes_exist):
    # 今日のことば：縦書きで掲げるので、英字が主の言葉は選ばない
    current_top = [w for w in W if w["層"] == "いちばん上" and not w["old"] and not mostly_latin(w["言葉"])]
    pool = current_top or [w for w in W if not w["old"]]
    today = pool[TODAY.toordinal() % len(pool)]
    fns = []

    def fn(w):
        u = w["出典URL"]
        if u not in fns:
            fns.append(u)
        return fns.index(u) + 1

    tn = fn(today)
    recent = sorted(W, key=lambda w: (w["checked"] or datetime.date.min, w["no"]), reverse=True)[:6]
    rows = []
    for w in recent:
        n = fn(w)
        chip = '<span class="chip kai">改定</span>' if w["前の言葉のID"] else f'<span class="chip">{esc(w["会社での呼び名"])}</span>'
        rows.append(f'<li><a href="{w["co"]["url"]}#{w["ID"]}"><span class="no">{w["no"]:03d}</span><span><span class="w">{esc(w["言葉"])}<sup class="fn">{n}</sup></span><span class="who">{esc(w["co"]["short"])}</span></span>{chip}</a></li>')
    names = stats["names"].most_common(4)
    nmax = names[0][1] if names else 1
    toks = stats["tokens"][:4]
    tmax = toks[0][1] if toks else 1
    hist = stats["length_hist"]
    hmax = max(hist["bins"]) or 1
    hi = hist["bins"].index(max(hist["bins"]))
    notes = "".join(f'<li><a href="{esc(u)}" rel="noopener" target="_blank">{esc(src_label(next(w for w in W if w["出典URL"] == u)))}</a></li>' for u in fns)
    hi_attr = ' class="hi"'
    hist_bars = "".join(f'<i{hi_attr if i == hi else ""} style="height:{max(3, round(b / hmax * 100))}%"></i>' for i, b in enumerate(hist["bins"]))
    name_bars = "".join(f'<div class="bar"><span>{esc(k)}</span><i style="width:{round(v / nmax * 100)}%"></i><b>{v}</b></div>' for k, v in names)
    tok_bars = "".join(f'<div class="bar"><span>{esc(k)}</span><i style="width:{round(v / tmax * 100)}%"></i><b>{v}</b></div>' for k, v in toks)
    today_url, today_id, today_co = today["co"]["url"], today["ID"], today["co"]["会社名"]
    body = f"""
<div class="masthead rise">
  <div class="vol">{kanji_date(TODAY)}</div>
  <h1>{esc(CFG['name'])}</h1>
</div>
<ul class="ledger" aria-label="収蔵の数">
  <li><a href="words/"><b>{len(C)}</b><small>社</small></a></li>
  <li><a href="words/"><b>{len(W)}</b><small>語</small></a></li>
  <li><a href="history/"><b>{stats['changes']}</b><small>改定</small></a></li>
</ul>
<div class="cols">
  <a class="today rise" href="{today_url}#{today_id}" aria-label="今日のことば　{esc(today_co)}">
    <span class="day">今日のことば</span>
    <p class="{tate_class(today['言葉'])}">{esc(today['言葉'])}<span class="fn">{tn}</span></p>
    <span class="sig"><span class="who">{esc(today_co)}</span>{seal(today['会社での呼び名'])}</span>
  </a>
  <section>
    <h2 class="sec-h">新収蔵<a href="words/" aria-label="すべての言葉">→</a></h2>
    <ol class="index">{''.join(rows)}</ol>
  </section>
</div>
<div class="topics">
  <a class="topic" href="topics/#names"><h2>呼び名</h2><div class="bars">{name_bars}</div></a>
  <a class="topic" href="topics/#tokens"><h2>よく使われる語</h2><div class="bars">{tok_bars}</div></a>
  <a class="topic" href="topics/#length"><h2>言葉の長さ<span>平均</span><span class="big">{hist['avg']}<small>字</small></span></h2>
    <div class="hist">{hist_bars}</div>
    <div class="hist-axis"><span>{hist['min']}字</span><span>{hist['max']}字</span></div></a>
</div>
<div class="notes-fn"><ol>{notes}</ol></div>
"""
    write("", page("", CFG["name"], body, notes_exist=notes_exist))


# ---------- 会社のページ ----------
def build_company(c, C, ids, token_df, notes_exist):
    ws = c["words"]
    fn = {u: i + 1 for i, u in enumerate(c["srcs"])}
    cur = [w for w in ws if not w["old"]]
    tops = [w for w in cur if w["層"] == "いちばん上"]
    visions = [w for w in cur if w["層"] == "目指す姿"]
    vals = OrderedDict()
    for w in cur:
        if w["層"] == "価値観":
            vals.setdefault(w["会社での呼び名"], []).append(w)
    parts = []
    for w in tops:
        ok = f'<a class="ok" href="#src{fn[w["出典URL"]]}" title="{esc(w["確認日"])}に出典で原文どおりと確かめた">✓ {dot(w["checked"])}</a>' if w["checked"] else ""
        parts.append(f'<figure class="scroll rise" id="{w["ID"]}"><p class="{tate_class(w["言葉"])}">{esc(w["言葉"])}<a class="fn" href="#src{fn[w["出典URL"]]}">{fn[w["出典URL"]]}</a></p><div class="foot">{seal(w["会社での呼び名"])}{ok}</div></figure>')
    for w in visions:
        parts.append(f'<section class="sec" id="{w["ID"]}"><p class="label">{esc(w["会社での呼び名"])}</p><p class="vision">{esc(w["言葉"])}<sup class="fn"><a class="fn" href="#src{fn[w["出典URL"]]}">{fn[w["出典URL"]]}</a></sup></p></section>')
    if vals:
        gl = []
        for name, g in vals.items():
            n = fn[g[0]["出典URL"]]
            lis = "".join('<li id="%s">%s</li>' % (w["ID"], esc(w["言葉"])) for w in g)
            gl.append(f'<div class="valgroup"><h2>{esc(name)}<sup class="fn"><a class="fn" href="#src{n}">{n}</a></sup></h2><ol>{lis}</ol></div>')
        groups = "".join(gl)
        parts.append(f'<section class="sec"><div class="vals{" two" if len(vals) == 2 else ""}">{groups}</div></section>')
    # 言語史
    chains = []
    byid = {w["ID"]: w for w in ws}
    for w in ws:
        if w["前の言葉のID"] and w["前の言葉のID"] in byid:
            chain = [w]
            while chain[0]["前の言葉のID"] in byid and byid[chain[0]["前の言葉のID"]] not in chain:
                chain.insert(0, byid[chain[0]["前の言葉のID"]])
            chains.append(chain)
    ended = [w for w in ws if w["使い終わり"] and not any(w in ch for ch in chains)]
    if chains or ended:
        items = []
        for ch in chains:
            for w in ch:
                start, end = ym(w["使い始め"]), ym(w["使い終わり"])
                when = f"{start}〜{end}" if (start or end) else ""
                items.append(f'<li class="{"old" if w["old"] else "now"}" id="{w["ID"] if w["old"] else ""}"><div class="when">{esc(when)}　{esc(w["会社での呼び名"])}<sup class="fn"><a class="fn" href="#src{fn[w["出典URL"]]}">{fn[w["出典URL"]]}</a></sup></div><div class="w">{esc(w["言葉"])}</div></li>')
        for w in ended:
            items.append(f'<li class="old" id="{w["ID"]}"><div class="when">〜{esc(ym(w["使い終わり"]))}　{esc(w["会社での呼び名"])}</div><div class="w">{esc(w["言葉"])}</div></li>')
        parts.append(f'<section class="sec"><p class="label">言語史</p><ol class="timeline">{"".join(items)}</ol></section>')
    # 出典
    srcs = []
    for u, n in fn.items():
        w = next(x for x in ws if x["出典URL"] == u)
        d = max((x["checked"] for x in ws if x["出典URL"] == u and x["checked"]), default=None)
        srcs.append(f'<li id="src{n}"><span class="n">{n}</span><a href="{esc(u)}" rel="noopener" target="_blank">{esc(src_label(w))}</a><span class="d">{"✓ " + dot(d) if d else ""}</span></li>')
    parts.append(f'<section class="sec"><p class="label">出典</p><ol class="srcs">{"".join(srcs)}</ol></section>')
    # 近い言葉：共通する語のうち、使っている会社が少ない（＝特徴的な）語で結ぶ
    near = []
    for o in C.values():
        if o["ID"] == c["ID"]:
            continue
        shared = c["tokens"] & o["tokens"]
        if shared:
            best = min(shared, key=lambda t: (token_df[t], t))
            near.append((len(shared), -token_df[best], o, best))
    near.sort(key=lambda x: (-x[0], x[1], x[2]["ID"]))
    if near:
        cards = "".join(f'<a href="../../{o["url"]}"><mark>{esc(t)}</mark>{esc(o["short"])}</a>' for _, _, o, t in near[:4])
        parts.append(f'<section class="sec"><p class="label">近い言葉</p><div class="related">{cards}</div></section>')
    i = ids.index(c["ID"])
    prev_c, next_c = C[ids[i - 1]], C[ids[(i + 1) % len(ids)]]
    contact = CFG.get("contact_url") or CFG["operator_url"]
    parts.append(f"""<div class="actions">
  <button class="icon-btn share" type="button" aria-label="このページを共有"><svg viewBox="0 0 24 24"><path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7M16 6l-4-4-4 4M12 2v13"/></svg></button>
  <a class="icon-btn" href="{esc(contact)}" rel="noopener" target="_blank" aria-label="訂正を知らせる"><svg viewBox="0 0 24 24"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg></a>
  <button class="icon-btn dice" type="button" aria-label="ほかの会社をひく">🎲</button>
</div>
<nav class="pager" aria-label="前後の会社"><a href="../../{prev_c['url']}">← {esc(prev_c['short'])}</a><a href="../../{next_c['url']}">{esc(next_c['short'])} →</a></nav>""")
    chips = [c.get("証券コード") or "", f"{len(ws)}語"]
    head = f"""<nav class="crumbs" aria-label="現在地"><a href="../../">{esc(CFG['name'])}</a> › <a href="../../words/">ことば</a> › {esc(c['会社名'])}</nav>
<div class="co-head"><h1>{esc(c['会社名'])}</h1><div class="chips">{''.join(f'<span class="chip line">{esc(x)}</span>' for x in chips if x)}</div></div>"""
    lead = tops[0]["言葉"] if tops else (cur[0]["言葉"] if cur else "")
    desc = f"{c['会社名']}が掲げる言葉。{lead[:80]}"
    write(c["url"], page(c["url"], c["会社名"], head + "\n".join(parts), desc=desc, notes_exist=notes_exist))


# ---------- ことばを探す ----------
def build_words(C, W, notes_exist):
    cur = [w for w in W if not w["old"]]
    layer_n = Counter(w["層"] for w in cur)
    items = []
    for w in sorted(cur, key=lambda w: (LAYERS.index(w["層"]) if w["層"] in LAYERS else 9, w["co"]["ID"], w["order"])):
        hay = unicodedata.normalize("NFKC", f"{w['言葉']} {w['co']['会社名']} {w['会社での呼び名']}").lower()
        items.append(f'<li data-layer="{esc(w["層"])}" data-s="{esc(hay)}"><a href="../{w["co"]["url"]}#{w["ID"]}"><span class="w">{esc(w["言葉"])}</span><span class="chip">{esc(w["会社での呼び名"])}</span><span class="who">{esc(w["co"]["会社名"])}</span></a></li>')
    btns = "".join(f'<button type="button" data-layer="{esc(l)}" aria-pressed="false">{esc(l)}<small>{layer_n[l]}</small></button>' for l in LAYERS if layer_n[l])
    body = f"""<div class="page-head"><h1>ことばを探す</h1></div>
<div class="finder">
  <form class="searchbox" role="search" onsubmit="return false"><input id="q" type="search" placeholder="挑戦、社会、誠実…" aria-label="言葉の中の語で探す" autocomplete="off"></form>
  <div class="filters" id="layers">{btns}</div>
  <p class="hits" aria-live="polite"><b id="n">{len(cur)}</b>語</p>
  <ul class="wordlist" id="list">{''.join(items)}</ul>
  <p class="empty" id="empty" hidden>見つかりません</p>
</div>
<script src="../assets/find.js?v={VER}" defer></script>"""
    write("words/", page("words/", "ことばを探す", body, current="words/", notes_exist=notes_exist, desc="会社が掲げる言葉を、言葉の中の語で探せます。"))


# ---------- 語のページ ----------
def build_token_pages(C, W, token_map, notes_exist):
    made = {}
    for t, ws in token_map.items():
        cos = {w["co"]["ID"] for w in ws}
        if len(cos) < 2:
            continue
        slug = urllib.parse.quote(t, safe="")
        made[t] = f"w/{slug}/"
        rows = []
        for w in sorted(ws, key=lambda w: (w["co"]["ID"], w["no"])):
            hl = esc(w["言葉"])
            norm = unicodedata.normalize("NFKC", w["言葉"])
            if t in w["言葉"]:
                hl = hl.replace(esc(t), f"<mark>{esc(t)}</mark>")
            elif t in norm.lower():
                pass
            rows.append(f'<li><a href="../../{w["co"]["url"]}#{w["ID"]}"><span class="w">{hl}</span><span class="chip">{esc(w["会社での呼び名"])}</span><span class="who">{esc(w["co"]["会社名"])}</span></a></li>')
        body = f"""<nav class="crumbs" aria-label="現在地"><a href="../../">{esc(CFG['name'])}</a> › <a href="../../topics/#tokens">よく使われる語</a></nav>
<div class="page-head"><h1>「{esc(t)}」</h1><div class="count"><b>{len(cos)}</b>社　<b>{len(ws)}</b>語</div></div>
<div class="finder"><ul class="wordlist">{''.join(rows)}</ul></div>"""
        # フォルダ名は日本語のまま（GitHub Pages は URL の %エンコードを戻してからファイルを探す）。リンクは %エンコードした made[t]
        write(f"w/{t}/", page(made[t], f"「{t}」を含む言葉", body, notes_exist=notes_exist, desc=f"「{t}」を掲げる言葉に使っている会社は{len(cos)}社。"))
    return made


# ---------- 研究テーマ ----------
def ending_kind(text):
    t = re.sub(r"[。．\.！!」』）\)\s]+$", "", unicodedata.normalize("NFKC", text))
    if not t:
        return "その他"
    if re.fullmatch(r"[\x00-\x7f–’‘\-]+", t):
        return "英語"
    last = t[-1]
    if last == "へ":
        return "「へ」で終わる"
    if last in "るすうくぐつぬぶむ":
        return "動詞で終わる"
    if last in "にをとで":
        return "助詞で終わる"
    return "名詞で終わる"


def build_topics(C, W, stats, token_pages, notes_exist):
    names = stats["names"].most_common()
    nmax = names[0][1] if names else 1
    toks = stats["tokens"][:20]
    tmax = toks[0][1] if toks else 1
    cloud = "".join(
        f'<a href="../{token_pages[t]}" style="font-size:{14 + round(v / tmax * 18)}px">{esc(t)}<small>{v}</small></a>'
        for t, v in stats["tokens"] if t in token_pages)
    hist = stats["length_hist"]
    hmax = max(hist["bins"]) or 1
    tops = stats["tops"]
    shortest = sorted(tops, key=lambda w: (len(w["言葉"]), w["no"]))[:3]
    longest = sorted(tops, key=lambda w: (-len(w["言葉"]), w["no"]))[:3]
    ex = lambda ws: "".join(f'<a href="../{w["co"]["url"]}#{w["ID"]}"><span>{esc(w["言葉"])}</span><small>{len(w["言葉"])}字　{esc(w["co"]["short"])}</small></a>' for w in ws)
    endings = Counter(ending_kind(w["言葉"]) for w in tops).most_common()
    emax = endings[0][1] if endings else 1
    vcount = Counter(len(g) for g in stats["value_groups"])
    vrows = sorted(vcount.items())
    vmax = max(vcount.values()) if vcount else 1
    body = f"""<div class="page-head"><h1>研究テーマ</h1></div>
<div class="study">
<section id="names"><h2>呼び名<small>いちばん上の言葉を何と呼ぶか　{len(tops)}社</small></h2>
  <div class="bars">{''.join(f'<div class="bar"><span>{esc(k)}</span><i style="width:{round(v / nmax * 100)}%"></i><b>{v}</b></div>' for k, v in names)}</div></section>
<section id="tokens"><h2>よく使われる語<small>使っている会社の数</small></h2>
  <div class="bars">{''.join(f'<a class="bar" href="../{token_pages[k]}"><span>{esc(k)}</span><i style="width:{round(v / tmax * 100)}%"></i><b>{v}</b></a>' if k in token_pages else f'<div class="bar"><span>{esc(k)}</span><i style="width:{round(v / tmax * 100)}%"></i><b>{v}</b></div>' for k, v in toks)}</div>
  <div class="cloud" style="margin-top:var(--space-8)">{cloud}</div></section>
<section id="length"><h2>言葉の長さ<small>いちばん上の言葉</small><span class="big">{hist['avg']}<small>字</small></span></h2>
  <div class="hist">{''.join(f'<i style="height:{max(3, round(b / hmax * 100))}%" title="{b}"></i>' for b in hist['bins'])}</div>
  <div class="hist-axis"><span>{hist['min']}字</span><span>{hist['max']}字</span></div>
  <div class="examples">{ex(shortest)}</div>
  <div class="examples">{ex(longest)}</div></section>
<section id="endings"><h2>文末の形<small>いちばん上の言葉</small></h2>
  <div class="bars">{''.join(f'<div class="bar"><span>{esc(k)}</span><i style="width:{round(v / emax * 100)}%"></i><b>{v}</b></div>' for k, v in endings)}</div></section>
<section id="values"><h2>価値観の項目数<small>ひとまとまりの価値観にいくつ並べるか</small></h2>
  <div class="bars">{''.join(f'<div class="bar"><span>{n}項目</span><i style="width:{round(v / vmax * 100)}%"></i><b>{v}</b></div>' for n, v in vrows)}</div></section>
</div>"""
    write("topics/", page("topics/", "研究テーマ", body, current="topics/", notes_exist=notes_exist, desc="会社が掲げる言葉を数えて見えた傾向。呼び名、よく使われる語、言葉の長さ、文末の形。"))


# ---------- 言語史 ----------
def build_history(C, W, notes_exist):
    byid = {w["ID"]: w for w in W}
    pairs = [(byid[w["前の言葉のID"]], w) for w in W if w["前の言葉のID"] in byid]
    pairs.sort(key=lambda p: (p[1]["使い始め"] or "", p[1]["no"]), reverse=True)
    items = "".join(f"""<li class="change rise">
  <div class="co"><a href="../{n['co']['url']}">{esc(n['co']['会社名'])}</a><span class="chip kai">{esc(ym(n['使い始め']) or '改定')}</span></div>
  <div class="old">{esc(o['言葉'])}<span class="when">{esc(o['会社での呼び名'])}</span></div>
  <div class="arrow" aria-label="改めた">→</div>
  <div class="new">{esc(n['言葉'])}<span class="when">{esc(n['会社での呼び名'])}</span></div>
</li>""" for o, n in pairs)
    body = f"""<div class="page-head"><h1>言語史</h1><div class="count"><b>{len(pairs)}</b>件</div></div>
<ol class="hist-list">{items}</ol>"""
    write("history/", page("history/", "言語史", body, current="history/", notes_exist=notes_exist, desc="会社が掲げる言葉を改めた記録。古い言葉と新しい言葉を並べています。"))


# ---------- 研究ノート ----------
def md_to_html(md):
    out, para, lst = [], [], None

    def inline(s):
        s = esc(s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        return s

    def flush():
        nonlocal para, lst
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para = []
        if lst:
            out.append(f"<{lst[0]}>" + "".join(f"<li>{inline(x)}</li>" for x in lst[1]) + f"</{lst[0]}>")
            lst = None

    for line in md.splitlines():
        s = line.rstrip()
        if not s:
            flush()
        elif s.startswith("### "):
            flush(); out.append(f"<h3>{inline(s[4:])}</h3>")
        elif s.startswith("## "):
            flush(); out.append(f"<h2>{inline(s[3:])}</h2>")
        elif s.startswith("> "):
            flush(); out.append(f"<blockquote>{inline(s[2:])}</blockquote>")
        elif re.match(r"^[-*] ", s):
            if para:
                flush()
            if not lst or lst[0] != "ul":
                flush(); lst = ["ul", []]
            lst[1].append(s[2:])
        elif re.match(r"^\d+\. ", s):
            if para:
                flush()
            if not lst or lst[0] != "ol":
                flush(); lst = ["ol", []]
            lst[1].append(re.sub(r"^\d+\. ", "", s))
        else:
            para.append(s)
    flush()
    return "\n".join(out)


def load_notes():
    d = os.path.join(ROOT, "notes")
    notes = []
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not f.endswith(".md") or f.startswith("_"):
            continue
        text = open(os.path.join(d, f), encoding="utf-8").read()
        meta = {}
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if m:
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            text = text[m.end():]
        if meta.get("公開") == "いいえ":
            continue
        meta["slug"] = f[:-3]
        meta["body"] = text
        notes.append(meta)
    notes.sort(key=lambda n: n.get("日付", ""), reverse=True)
    return notes


def build_notes(notes):
    if not notes:
        return
    lis = "".join(f'<li><a href="{n["slug"]}/"><span class="t">{esc(n.get("題", n["slug"]))}</span><span class="d">{esc(n.get("日付", ""))}</span></a></li>' for n in notes)
    write("notes/", page("notes/", "研究ノート", f'<div class="page-head"><h1>研究ノート</h1></div><ul class="note-list">{lis}</ul>', current="notes/"))
    for n in notes:
        body = f"""<nav class="crumbs" aria-label="現在地"><a href="../../">{esc(CFG['name'])}</a> › <a href="../">研究ノート</a></nav>
<div class="page-head"><h1>{esc(n.get('題', ''))}</h1><p class="byline">{esc(n.get('日付', ''))}　{esc(CFG['operator'])}</p></div>
<article class="prose">{md_to_html(n['body'])}</article>"""
        write(f"notes/{n['slug']}/", page(f"notes/{n['slug']}/", n.get("題", ""), body, current="notes/", desc=n.get("説明")))


# ---------- この研究所について ----------
def build_about(C, W, notes_exist):
    contact = CFG.get("contact_url") or CFG["operator_url"]
    body = f"""<div class="page-head"><h1>この研究所について</h1></div>
<article class="prose">
<blockquote>{esc(CFG['subtitle'])}</blockquote>
<h2>集め方</h2>
<ol class="steps">
  <li>有価証券報告書の「経営方針」の欄、会社の公式サイト、公式の発表から言葉を探す</li>
  <li>言葉を原文どおりに写す（全角・半角や記号も変えない）</li>
  <li>出典をもう一度開き、一字一句照らしてから載せる</li>
  <li>載せたあとも理念のページを見直し、言葉が改められたら古い言葉を残して新しい言葉を足す</li>
</ol>
<h2>層</h2>
<p><strong>いちばん上</strong>　ミッション、パーパス、経営理念、綱領など、会社の言葉の頂点にあるもの<br>
<strong>目指す姿</strong>　ビジョン<br>
<strong>価値観</strong>　バリュー、行動指針、社是・社訓など、短い項目が並ぶもの</p>
<h2>数え方</h2>
<p>研究テーマの「よく使われる語」は、言葉から漢字の2〜4字の並び、カタカナの3字以上、英字の4字以上を取り出し、その語を使っている会社の数を数えています。</p>
<h2>訂正・取り下げ</h2>
<p>誤りや新しい言葉に気づいたら、<a href="{esc(contact)}" rel="noopener" target="_blank">運営者の連絡先</a>からお知らせください。出典で確かめたうえで直します。</p>
<h2>運営</h2>
<p>{esc(CFG['operator'])}（コミュニティ研究家・キャリア研究家）。<a href="https://community-zukan.github.io/">コミュニティ図鑑</a>、<a href="https://ashitano-tenki.github.io/">あしたの転機観測所</a>も運営しています。</p>
</article>"""
    write("about/", page("about/", "この研究所について", body, current="about/", notes_exist=notes_exist, desc="会社のことば研究所の集め方と数え方。"))


# ---------- 集計 ----------
def compute_stats(C, W):
    tops = [w for w in W if w["層"] == "いちばん上" and not w["old"]]
    names = Counter()
    for c in C.values():
        for n in {w["会社での呼び名"] for w in c["words"] if w["層"] == "いちばん上" and not w["old"]}:
            names[n] += 1
    token_map = defaultdict(list)
    for w in W:
        if not w["old"]:
            for t in w["tokens"]:
                token_map[t].append(w)
    token_df = {t: len({w["co"]["ID"] for w in ws}) for t, ws in token_map.items()}
    ranked = sorted(token_df.items(), key=lambda x: (-x[1], x[0]))
    lens = [len(w["言葉"]) for w in tops] or [0]
    lo, hi = min(lens), max(lens)
    nb = 7
    width = max(1, -(-(hi - lo + 1) // nb))
    bins = [0] * nb
    for L in lens:
        bins[min(nb - 1, (L - lo) // width)] += 1
    groups = defaultdict(list)
    for w in W:
        if w["層"] == "価値観" and not w["old"]:
            groups[(w["co"]["ID"], w["会社での呼び名"])].append(w)
    return {
        "tops": tops, "names": names, "tokens": ranked, "token_map": token_map, "token_df": token_df,
        "length_hist": {"avg": round(sum(lens) / len(lens)), "min": lo, "max": hi, "bins": bins},
        "changes": sum(1 for w in W if w["前の言葉のID"]),
        "value_groups": list(groups.values()),
    }


def build_misc(C, W, token_pages, notes):
    urls = ["", "words/", "topics/", "history/", "about/"] + [c["url"] for c in C.values()] + list(token_pages.values())
    if notes:
        urls += ["notes/"] + [f"notes/{n['slug']}/" for n in notes]
    sm = "".join(f"<url><loc>{esc(BASE + u)}</loc></url>" for u in urls)
    open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8").write(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>')
    open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8").write(f"User-agent: *\nAllow: /\nSitemap: {BASE}sitemap.xml\n")
    json.dump([c["url"] for c in C.values()], open(os.path.join(OUT, "pick.json"), "w", encoding="utf-8"))
    pub = [{k: w[k] for k in WORD_COLS} for w in W]
    json.dump({"updated": TODAY.isoformat(), "count": len(pub), "words": pub}, open(os.path.join(OUT, "words.json"), "w", encoding="utf-8"), ensure_ascii=False)
    write("404.html", page("404.html", "見つかりません", '<div class="page-head"><h1>見つかりません</h1></div><p style="text-align:center"><a href="/">トップへ</a>　<a href="/words/">ことばを探す</a></p>'))
    open(os.path.join(OUT, ".nojekyll"), "w").write("")


def main():
    words, comps = load()
    C = model(words, comps)
    W = [w for c in C.values() for w in c["words"]]
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(OUT, "assets"))
    notes = load_notes()
    ne = bool(notes)
    stats = compute_stats(C, W)
    build_top(C, W, stats, ne)
    ids = list(C.keys())
    for c in C.values():
        build_company(c, C, ids, stats["token_df"], ne)
    build_words(C, W, ne)
    token_pages = build_token_pages(C, W, stats["token_map"], ne)
    build_topics(C, W, stats, token_pages, ne)
    build_history(C, W, ne)
    build_notes(notes)
    build_about(C, W, ne)
    build_misc(C, W, token_pages, notes)
    print(f"会社 {len(C)}　言葉 {len(W)}　改定 {stats['changes']}　語のページ {len(token_pages)}　研究ノート {len(notes)}")
    print("よく使われる語:", ", ".join(f"{t}({n})" for t, n in stats["tokens"][:12]))


if __name__ == "__main__":
    main()
