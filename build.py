"""会社のことば研究所のサイトを作る。Python の標準ライブラリだけで動く（pykakasi があれば、ひらがな検索用の読みを足す）。

使い方:
  python3 build.py                      # config/site.json の CSV の URL から読む（空なら data/ の写し）
  python3 build.py --words testdata/words.csv --companies testdata/companies.csv   # 手元のCSVで試す
出力は _site/。手元のCSVで試したときは data/ を書き換えない。
共有画像は、このあと tools/make_og.py が _site/og/jobs.json を読んで作る。
"""
import csv, datetime, html, io, json, os, re, shutil, sys, unicodedata, urllib.parse, urllib.request
from collections import Counter, defaultdict, OrderedDict

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "_site")
JST = datetime.timezone(datetime.timedelta(hours=9))
NOW = datetime.datetime.now(JST)
TODAY = NOW.date()
esc = html.escape
q = urllib.parse.quote
CFG = json.load(open(os.path.join(ROOT, "config", "site.json"), encoding="utf-8"))
SYN = json.load(open(os.path.join(ROOT, "config", "synonyms.json"), encoding="utf-8")) if os.path.exists(os.path.join(ROOT, "config", "synonyms.json")) else []
BASE = CFG["base_url"].rstrip("/") + "/"
VER = NOW.strftime("%Y%m%d%H%M")

WORD_COLS = ["ID", "会社ID", "会社名", "対象", "層", "会社での呼び名", "項目の順番", "言葉", "英語版", "使い始め", "使い終わり", "前の言葉のID", "出典URL", "出典の種類", "出典の日付", "確認日"]
COMPANY_COLS = ["ID", "会社名", "読み", "証券コード", "EDINETコード", "業種", "上場区分", "設立年", "公式サイト", "理念ページのURL"]
LAYERS = ["いちばん上", "目指す姿", "価値観"]
# シートの「層」の値はそのまま、サイトでは次の名前で見せる（2026-11-08 黒田さんの決定）
LAYER_LABEL = {"いちばん上": "北極星", "目指す姿": "理想像", "価値観": "価値観"}
HISTORY_MIN = 5   # 公開中の改定がこの数になるまで、言語史をメニューとサイトマップに出さない
AI_TRAINING = ["GPTBot", "ClaudeBot", "anthropic-ai", "Google-Extended", "CCBot", "Applebot-Extended", "Meta-ExternalAgent", "Bytespider", "cohere-training-data-crawler"]
SISTERS = [("コミュニティ図鑑", "https://community-zukan.github.io/", "zukan"),
           ("あしたの転機観測所", "https://ashitano-tenki.github.io/", "kansoku"),
           ("現代曖昧単語辞典", "https://gendai-aimai-tango-jiten.github.io/", "jiten")]

try:
    import pykakasi
    KKS = pykakasi.kakasi()
except Exception:
    KKS = None


def label(layer):
    return LAYER_LABEL.get(layer, layer)


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


STOP = {"当社", "弊社", "我等", "我々", "私達", "以下", "全て", "一人", "一人ひとり", "目指", "通じ", "提供", "実現"}
PUNCT = set("、。，．,.・「」『』（）()［］[]【】〈〉《》！？!?：:；;“”\"'’‘–—-―…～〜/／")


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


def mostly_latin(text):
    letters = [ch for ch in text if not ch.isspace()]
    return bool(letters) and sum(1 for ch in letters if ord(ch) < 0x3000) / len(letters) > 0.5


def char_len(text):
    """字数：空白・句読点・括弧・記号は数えない（2026-11-08。「言葉の長さ」の数え方）"""
    return sum(1 for ch in unicodedata.normalize("NFKC", text) if not ch.isspace() and ch not in PUNCT)


def latin_words(text):
    return len(re.findall(r"[A-Za-z]+", text))


def yomi(text):
    if not KKS:
        return ""
    try:
        return "".join(x["hira"] for x in KKS.convert(text))
    except Exception:
        return ""


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
        w["latin"] = mostly_latin(w["言葉"])
        w["len"] = char_len(w["言葉"])
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
        reading = c.get("読み") or yomi(c["short"])
        c["search"] = unicodedata.normalize("NFKC", f"{c['会社名']} {c['short']} {reading}").lower()
    return C


def src_label(w):
    m = re.search(r"\?(S[0-9A-Z]{7})$", w["出典URL"])
    kind = w["出典の種類"] or "出典"
    d = pdate(w["出典の日付"])
    when = f"{d.year}年{d.month}月{d.day}日提出" if d and kind == "有価証券報告書" else (f"{d.year}年{d.month}月{d.day}日" if d else "")
    tail = f"（EDINET {m.group(1)}）" if m else ""
    return " ".join(x for x in [kind, when] if x) + tail


def contact_url(target=""):
    """訂正・ご意見のフォーム。対象（会社名とページのURL）を入れた状態で開く"""
    url = CFG.get("contact_url") or CFG["operator_url"]
    entry = CFG.get("contact_target_entry")
    if CFG.get("contact_url") and entry and target:
        url += ("&" if "?" in url else "?") + f"usp=pp_url&{entry}={q(target)}"
    return url


# ---------- ページの枠 ----------
def nav_items(show_history, notes_exist):
    items = [("words/", "ことばを探す"), ("topics/", "統計")]
    if show_history:
        items.append(("history/", "言語史"))
    if notes_exist:
        items.append(("notes/", "研究ノート"))
    items.append(("about/", "この研究所について"))
    return items


SITE = {"show_history": False, "notes_exist": False}


def ext(url, text, click=""):
    """外部サイトへの文字のリンク。別のタブで開き、CSS が「↗」を付ける"""
    gc = f' data-goatcounter-click="{esc(click)}"' if click else ""
    return f'<a href="{esc(url)}" rel="noopener" target="_blank"{gc}>{text}</a>'


def page(path, title, body, desc=None, current=None, og=None, jsonld=None, noindex=False):
    depth = path.count("/")
    rel = "../" * depth
    full_title = f"{title}｜{CFG['name']}" if title != CFG["name"] else f"{CFG['name']}｜{CFG['subtitle']}"
    desc = desc or CFG["description"]
    canon = BASE + path
    cur_attr = ' aria-current="page"'
    items = nav_items(SITE["show_history"], SITE["notes_exist"])
    nav = "".join(f'<a href="{rel}{u}"{cur_attr if current == u else ""}>{esc(t)}</a>' for u, t in items)
    og_img = BASE + (og or "og/site.png")
    head_extra = ""
    gc = CFG.get("goatcounter")
    if gc:
        head_extra += f'<script data-goatcounter="https://{esc(gc)}.goatcounter.com/count" async src="{rel}assets/count.js?v={VER}"></script>\n'
    gsv = CFG.get("google_site_verification")
    if gsv and path == "":  # Search Console の確認（トップにだけ置けば足りる。消すと確認が外れる）
        head_extra += f'<meta name="google-site-verification" content="{esc(gsv)}">\n'
    if jsonld:
        head_extra += '<script type="application/ld+json">' + json.dumps(jsonld, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"
    if noindex:
        head_extra += '<meta name="robots" content="noindex">\n'
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>try{{var t=localStorage.getItem('kotoba-theme');if(t!=='dark')t='light';document.documentElement.dataset.theme=t}}catch(e){{}}</script>
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canon)}">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(canon)}">
<meta property="og:type" content="{'article' if path.startswith('notes/') and path != 'notes/' else 'website'}">
<meta property="og:site_name" content="{esc(CFG['name'])}">
<meta property="og:image" content="{esc(og_img)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#ffffff">
<link rel="icon" href="{rel}assets/icon.svg" type="image/svg+xml">
<link rel="icon" href="{rel}assets/favicon-32.png" sizes="32x32">
<link rel="apple-touch-icon" href="{rel}assets/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Shippori+Mincho+B1:wght@500;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{rel}assets/style.css?v={VER}">
{head_extra}</head>
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
  <nav aria-label="フッター">{nav}<a href="{esc(contact_url())}" rel="noopener" target="_blank" data-goatcounter-click="contact/footer">訂正・ご意見</a></nav>
  <div class="footer-row"><small>運営　{ext(CFG['operator_url'], esc(CFG['operator']), 'operator/footer')}</small>
  <button class="theme-btn" type="button" aria-label="明るい表示と暗い表示を切り替える"><span class="to-dark">☾ 暗い表示</span><span class="to-light">☀ 明るい表示</span></button></div>
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
    """落款：4字以内の漢字の呼び名だけ。それ以外（長い呼び名・カタカナ・英字）は、枠のない朱色の縦書き1列"""
    t = re.sub(r"[（(].*?[）)]", "", text).strip()
    if re.fullmatch(r"[一-龥々]{1,4}", t):
        return f'<span class="seal">{esc(t)}</span>'
    if re.fullmatch(r"[\x00-\x7f]+", t):
        return f'<span class="seal-line latin">{esc(t)}</span>'
    return f'<span class="seal-line">{esc(t)}</span>'


def word_block(w, fn_html):
    """掛け軸・今日のことばの言葉。英字が主の言葉は横書き（2026-11-08）"""
    if w["latin"]:
        return f'<p class="yoko">{esc(w["言葉"])}{fn_html}</p>'
    cls = "tate long" if w["len"] > 36 else "tate"
    return f'<p class="{cls}">{esc(w["言葉"])}{fn_html}</p>'


SHARE_ICONS = {
    "x": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4l16 16M20 4L4 20" /></svg>',
    "facebook": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 8h3V4h-3a4 4 0 0 0-4 4v3H7v4h3v6h4v-6h3l1-4h-4V8z"/></svg>',
    "threads": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16.5 11.5c-.4-3-2.4-4.5-5-4.5-3 0-5 2.2-5 5.3 0 3.4 2.2 5.7 5.5 5.7 2.6 0 4.6-1.4 4.6-3.6 0-2-1.8-3.2-4.2-3.2-1.8 0-3 .9-3 2.1 0 1 .9 1.7 2.1 1.7 2 0 3-1.5 3-4.5"/></svg>',
    "copy": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/></svg>',
}


def share_row(path, text, key):
    url = BASE + path
    links = [
        ("x", "X", f"https://twitter.com/intent/tweet?text={q(text)}&url={q(url)}"),
        ("facebook", "Facebook", f"https://www.facebook.com/sharer/sharer.php?u={q(url)}"),
        ("threads", "Threads", f"https://www.threads.net/intent/post?text={q(text + ' ' + url)}"),
    ]
    a = "".join(f'<a class="share-btn" href="{esc(h)}" rel="noopener" target="_blank" data-goatcounter-click="share/{k}/{esc(key)}">{SHARE_ICONS[k]}<span>{n}</span></a>' for k, n, h in links)
    b = f'<button class="share-btn copy" type="button" data-url="{esc(url)}" data-goatcounter-click="share/copy/{esc(key)}">{SHARE_ICONS["copy"]}<span>リンクをコピー</span></button>'
    return f'<div class="share" aria-label="共有">{a}{b}</div>'


# ---------- 言葉の長さ（トップの小さな図と統計のページで共通） ----------
def length_data(stats):
    ws = stats["length_words"]
    if not ws:
        return None
    lens = sorted(w["len"] for w in ws)
    lo, hi = lens[0], lens[-1]
    n = len(lens)
    med = lens[n // 2] if n % 2 else (lens[n // 2 - 1] + lens[n // 2]) / 2
    avg = sum(lens) / n
    return {"words": ws, "min": lo, "max": hi, "avg": avg, "med": med}


def pos(v, lo, hi):
    return 0 if hi == lo else round((v - lo) / (hi - lo) * 100, 2)


def strip_html(ld, rel, big=False):
    """1社を1つの点にして字数の線に並べる。点を押すと、その言葉が下に出る（site.js）"""
    lo, hi = ld["min"], ld["max"]
    lanes = defaultdict(int)
    dots = []
    for w in sorted(ld["words"], key=lambda w: (w["len"], w["no"])):
        p = pos(w["len"], lo, hi)
        key = round(p / 3)
        lane = lanes[key]
        lanes[key] += 1
        dots.append(f'<button type="button" class="dot" style="left:{p}%;bottom:{lane * 14}px" '
                    f'data-id="{w["ID"]}" data-len="{w["len"]}" data-w="{esc(w["言葉"])}" data-co="{esc(w["co"]["short"])}" '
                    f'data-href="{rel}{w["co"]["url"]}#{w["ID"]}" aria-label="{w["len"]}字　{esc(w["co"]["short"])}"></button>')
    height = 28 + max(lanes.values()) * 14
    marks = (f'<span class="mark avg" style="left:{pos(ld["avg"], lo, hi)}%"><b>平均 {round(ld["avg"])}字</b></span>'
             f'<span class="mark med" style="left:{pos(ld["med"], lo, hi)}%"><b>中央値 {round(ld["med"])}字</b></span>') if big else ""
    step = 10 if hi - lo <= 120 else 20
    ticks = ""
    if big:
        t0 = (lo // step + 1) * step
        # 端の「○字」と重ならないように、両端から6%以内の目盛りは出さない
        ticks = "".join(f'<span class="tick" style="left:{pos(t, lo, hi)}%">{t}</span>' for t in range(t0, hi, step) if 6 < pos(t, lo, hi) < 94)
    return (f'<div class="strip{" big" if big else ""}" style="height:{height}px">{marks}{"".join(dots)}</div>'
            f'<div class="strip-axis"><span>{lo}字</span>{ticks}<span>{hi}字</span></div>')


# ---------- トップ ----------
def build_top(C, W, stats):
    current_top = [w for w in W if w["層"] == "いちばん上" and not w["old"]]
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
    name_bars = "".join(f'<div class="bar"><span>{esc(k)}</span><i style="width:{round(v / nmax * 100)}%"></i><b>{v}</b></div>' for k, v in names)
    tok_bars = "".join(f'<div class="bar"><span>{esc(k)}</span><i style="width:{round(v / tmax * 100)}%"></i><b>{v}</b></div>' for k, v in toks)
    ld = length_data(stats)
    length_html = ""
    if ld:
        length_html = f"""<section class="topic">
    <h2><a href="topics/#length">{label('いちばん上')}の長さ</a></h2>
    <div class="len-sum"><span>最短<b>{ld['min']}</b>字</span><span>平均<b>{round(ld['avg'])}</b>字</span><span>最長<b>{ld['max']}</b>字</span></div>
    {strip_html(ld, '')}
    <p class="dot-pick" aria-live="polite" hidden></p>
  </section>"""
    notes = "".join(f'<li>{ext(u, esc(src_label(next(w for w in W if w["出典URL"] == u))), "source/top")}</li>' for u in fns)
    today_url, today_id, today_co = today["co"]["url"], today["ID"], today["co"]["会社名"]
    body = f"""
<div class="masthead rise">
  <h1>{esc(CFG['name'])}</h1>
</div>
<ul class="ledger" aria-label="収蔵の数">
  <li><a href="words/"><b>{len(C)}</b><small>社</small></a></li>
  <li><a href="words/"><b>{len(W)}</b><small>語</small></a></li>
</ul>
<div class="cols">
  <a class="today{' latin' if today['latin'] else ''} rise" href="{today_url}#{today_id}" aria-label="今日のことば　{esc(today_co)}">
    <span class="day">今日のことば</span>
    {word_block(today, f'<span class="fn">{tn}</span>')}
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
  {length_html}
</div>
<div class="notes-fn"><ol>{notes}</ol></div>
"""
    jsonld = {"@context": "https://schema.org", "@type": "WebSite", "name": CFG["name"], "url": BASE, "description": CFG["description"],
              "publisher": {"@type": "Person", "name": CFG["operator"], "url": CFG["operator_url"]},
              "potentialAction": {"@type": "SearchAction", "target": BASE + "words/?q={search_term_string}", "query-input": "required name=search_term_string"}}
    write("", page("", CFG["name"], body, jsonld=jsonld))


# ---------- 会社のページ ----------
def build_company(c, C, ids, token_df, og_jobs):
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
        n = fn[w["出典URL"]]
        ok = f'<a class="ok" href="#src{n}" title="出典で原文どおりと確かめた日">✓ {dot(w["checked"])}</a>' if w["checked"] else ""
        block = word_block(w, fn_link(n))
        latin_cls = " latin" if w["latin"] else ""
        parts.append(f'<figure class="scroll{latin_cls} rise" id="{w["ID"]}">{block}<div class="foot">{seal(w["会社での呼び名"])}{ok}</div></figure>')
    for w in visions:
        n = fn[w["出典URL"]]
        parts.append(f'<section class="sec" id="{w["ID"]}"><p class="label">{esc(w["会社での呼び名"])}</p><p class="vision">{esc(w["言葉"])}<sup>{fn_link(n)}</sup></p></section>')
    if vals:
        gl = []
        for name, g in vals.items():
            n = fn[g[0]["出典URL"]]
            lis = "".join('<li id="%s">%s</li>' % (w["ID"], esc(w["言葉"])) for w in g)
            gl.append(f'<div class="valgroup"><h2>{esc(name)}<sup>{fn_link(n)}</sup></h2><ol>{lis}</ol></div>')
        parts.append(f'<section class="sec"><div class="vals{" two" if len(vals) == 2 else ""}">{"".join(gl)}</div></section>')
    # 言語史
    byid = {w["ID"]: w for w in ws}
    chains = []
    for w in ws:
        if w["前の言葉のID"] and w["前の言葉のID"] in byid and not w["old"]:
            chain = [w]
            while chain[0]["前の言葉のID"] in byid and byid[chain[0]["前の言葉のID"]] not in chain:
                chain.insert(0, byid[chain[0]["前の言葉のID"]])
            chains.append(chain)
    in_chain = {x["ID"] for ch in chains for x in ch}
    ended = [w for w in ws if w["使い終わり"] and w["ID"] not in in_chain]
    if chains or ended:
        items = []
        for ch in chains:
            for w in ch:
                start, end = ym(w["使い始め"]), ym(w["使い終わり"])
                when = f"{start}〜{end}" if (start or end) else ""
                wid = f' id="{w["ID"]}"' if w["old"] else ""
                items.append(f'<li class="{"old" if w["old"] else "now"}"{wid}><div class="when">{esc(when)}　{esc(w["会社での呼び名"])}<sup>{fn_link(fn[w["出典URL"]])}</sup></div><div class="w">{esc(w["言葉"])}</div></li>')
        for w in ended:
            items.append(f'<li class="old" id="{w["ID"]}"><div class="when">〜{esc(ym(w["使い終わり"]))}　{esc(w["会社での呼び名"])}</div><div class="w">{esc(w["言葉"])}</div></li>')
        parts.append(f'<section class="sec"><p class="label">言語史</p><ol class="timeline">{"".join(items)}</ol></section>')
    # 出典と訂正
    srcs = []
    for u, n in fn.items():
        w = next(x for x in ws if x["出典URL"] == u)
        d = max((x["checked"] for x in ws if x["出典URL"] == u and x["checked"]), default=None)
        srcs.append(f'<li id="src{n}"><span class="n">{n}</span>{ext(u, esc(src_label(w)), "source/" + c["ID"])}<span class="d">{"✓ " + dot(d) if d else ""}</span></li>')
    fix = ext(contact_url(f"{c['会社名']} {BASE}{c['url']}"), "この会社の言葉の訂正を送る", "contact/" + c["ID"])
    parts.append(f'<section class="sec"><p class="label">出典</p><ol class="srcs">{"".join(srcs)}</ol><p class="fix">{fix}</p></section>')
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
    lead_w = tops[0] if tops else (cur[0] if cur else ws[0])
    share_text = f"{c['会社名']}の{lead_w['会社での呼び名']}「{lead_w['言葉'][:60]}{'…' if len(lead_w['言葉']) > 60 else ''}」"
    parts.append(f'<section class="sec">{share_row(c["url"], share_text, c["ID"])}</section>')
    i = ids.index(c["ID"])
    prev_c, next_c = C[ids[i - 1]], C[ids[(i + 1) % len(ids)]]
    parts.append(f"""<nav class="pager" aria-label="前後の会社"><a href="../../{prev_c['url']}">← {esc(prev_c['short'])}</a><button class="dice" type="button" data-goatcounter-click="pick/{c['ID']}">🎲 ほかの会社</button><a href="../../{next_c['url']}">{esc(next_c['short'])} →</a></nav>""")
    chips = [c.get("証券コード") or "", f"{len(ws)}語"]
    head = f"""<nav class="crumbs" aria-label="現在地"><a href="../../">{esc(CFG['name'])}</a> › <a href="../../words/">ことば</a> › {esc(c['会社名'])}</nav>
<div class="co-head"><h1>{esc(c['会社名'])}</h1><div class="chips">{''.join(f'<span class="chip line">{esc(x)}</span>' for x in chips if x)}</div></div>"""
    desc = f"{c['会社名']}が掲げる言葉。{lead_w['言葉'][:80]}"
    jsonld = {"@context": "https://schema.org", "@type": "ItemList", "name": f"{c['会社名']}が掲げる言葉", "url": BASE + c["url"],
              "itemListElement": [{"@type": "ListItem", "position": k + 1, "item": {
                  "@type": "Quotation", "text": w["言葉"], "name": w["会社での呼び名"],
                  "creator": {"@type": "Organization", "name": c["会社名"]},
                  "citation": w["出典URL"]}} for k, w in enumerate(cur)]}
    og = f"og/c/{c['ID']}.png"
    og_jobs.append({"out": og, "kind": "company", "word": lead_w["言葉"], "latin": lead_w["latin"], "company": c["会社名"], "name": lead_w["会社での呼び名"]})
    write(c["url"], page(c["url"], c["会社名"], head + "\n".join(parts), desc=desc, og=og, jsonld=jsonld))


def fn_link(n):
    return f'<a class="fn" href="#src{n}">{n}</a>'


# ---------- ことばを探す ----------
def build_words(C, W, stats, token_pages):
    cur = [w for w in W if not w["old"]]
    layer_n = Counter(w["層"] for w in cur)
    items = []
    for w in sorted(cur, key=lambda w: (LAYERS.index(w["層"]) if w["層"] in LAYERS else 9, w["co"]["ID"], w["order"])):
        hay = unicodedata.normalize("NFKC", f"{w['言葉']} {w['会社での呼び名']} {yomi(w['言葉'])}").lower() + " " + w["co"]["search"]
        items.append(f'<li data-layer="{esc(w["層"])}" data-s="{esc(hay)}"><a href="../{w["co"]["url"]}#{w["ID"]}"><span class="w">{esc(w["言葉"])}</span><span class="chip">{esc(w["会社での呼び名"])}</span><span class="who">{esc(w["co"]["会社名"])}</span></a></li>')
    btns = "".join(f'<button type="button" data-layer="{esc(l)}" aria-pressed="false">{esc(label(l))}<small>{layer_n[l]}</small></button>' for l in LAYERS if layer_n[l])
    examples = [t for t, n in stats["tokens"] if t in token_pages][:12]
    searched = [s for s in CFG.get("searched_words", []) if s]
    ex_json = esc(json.dumps({"tokens": examples, "searched": searched}, ensure_ascii=False))
    body = f"""<div class="page-head"><h1>ことばを探す</h1></div>
<div class="finder">
  <form class="searchbox" role="search" onsubmit="return false"><input id="q" type="search" placeholder="挑戦、社会、誠実…" aria-label="言葉の中の語や社名で探す" autocomplete="off"></form>
  <p class="examples-row" id="ex" data-ex="{ex_json}" hidden></p>
  <div class="filters" id="layers">{btns}</div>
  <p class="hits" aria-live="polite"><b id="n">{len(cur)}</b>語</p>
  <ul class="wordlist" id="list">{''.join(items)}</ul>
  <p class="empty" id="empty" hidden>見つかりません</p>
</div>
<script>window.KOTOBA_SYN = {json.dumps(SYN, ensure_ascii=False)};</script>
<script src="../assets/find.js?v={VER}" defer></script>"""
    write("words/", page("words/", "ことばを探す", body, current="words/", desc="会社が掲げる言葉を、言葉の中の語や社名で探せます。"))


# ---------- 語のページ ----------
def build_token_pages(C, W, token_map):
    made = {}
    for t, ws in token_map.items():
        cos = {w["co"]["ID"] for w in ws}
        if len(cos) < 2:
            continue
        made[t] = f"w/{q(t, safe='')}/"
        rows = []
        for w in sorted(ws, key=lambda w: (w["co"]["ID"], w["no"])):
            hl = esc(w["言葉"])
            if t in w["言葉"]:
                hl = hl.replace(esc(t), f"<mark>{esc(t)}</mark>")
            rows.append(f'<li><a href="../../{w["co"]["url"]}#{w["ID"]}"><span class="w">{hl}</span><span class="chip">{esc(w["会社での呼び名"])}</span><span class="who">{esc(w["co"]["会社名"])}</span></a></li>')
        body = f"""<nav class="crumbs" aria-label="現在地"><a href="../../">{esc(CFG['name'])}</a> › <a href="../../topics/#tokens">統計</a></nav>
<div class="page-head"><h1>「{esc(t)}」</h1><div class="count"><b>{len(cos)}</b>社　<b>{len(ws)}</b>語</div></div>
<div class="finder"><ul class="wordlist">{''.join(rows)}</ul></div>"""
        # フォルダ名は日本語のまま（GitHub Pages は URL の %エンコードを戻してからファイルを探す）
        write(f"w/{t}/", page(made[t], f"「{t}」を含む言葉", body, desc=f"「{t}」を掲げる言葉に使っている会社は{len(cos)}社。"))
    return made


# ---------- 統計 ----------
def build_topics(C, W, stats, token_pages):
    names = stats["names"].most_common()
    nmax = names[0][1] if names else 1
    toks = stats["tokens"][:20]
    tmax = toks[0][1] if toks else 1
    cloud = "".join(
        f'<a href="../{token_pages[t]}" style="font-size:{14 + round(v / tmax * 18)}px">{esc(t)}<small>{v}</small></a>'
        for t, v in stats["tokens"] if t in token_pages)
    tok_bars = "".join(
        (f'<a class="bar" href="../{token_pages[k]}">' if k in token_pages else '<div class="bar">')
        + f'<span>{esc(k)}</span><i style="width:{round(v / tmax * 100)}%"></i><b>{v}</b>'
        + ("</a>" if k in token_pages else "</div>") for k, v in toks)
    name_bars = "".join(f'<div class="bar"><span>{esc(k)}</span><i style="width:{round(v / nmax * 100)}%"></i><b>{v}</b></div>' for k, v in names)
    ld = length_data(stats)
    length_sec = ""
    if ld:
        lo, hi = ld["min"], ld["max"]
        step = 10
        bins = []
        b0 = (lo // step) * step
        while b0 <= hi:
            n = sum(1 for w in ld["words"] if b0 <= w["len"] < b0 + step)
            if n:
                bins.append((b0, b0 + step - 1, n))
            b0 += step
        bin_btns = "".join(f'<button type="button" data-lo="{a}" data-hi="{b}" aria-pressed="false">{a}〜{b}字<small>{n}</small></button>' for a, b, n in bins)
        latin = stats["latin_tops"]
        if latin:
            bin_btns += f'<button type="button" data-latin="1" aria-pressed="false">英語<small>{len(latin)}</small></button>'
        rows = []
        for w in sorted(ld["words"], key=lambda w: (w["len"], w["no"])):
            rows.append(f'<li data-id="{w["ID"]}" data-len="{w["len"]}"><a href="../{w["co"]["url"]}#{w["ID"]}"><span class="n">{w["len"]}<small>字</small></span><span class="w">{esc(w["言葉"])}</span><span class="who">{esc(w["co"]["short"])}</span></a></li>')
        for w in latin:
            rows.append(f'<li data-id="{w["ID"]}" data-latin="1" hidden><a href="../{w["co"]["url"]}#{w["ID"]}"><span class="n">{latin_words(w["言葉"])}<small>語</small></span><span class="w">{esc(w["言葉"])}</span><span class="who">{esc(w["co"]["short"])}</span></a></li>')
        length_sec = f"""<section id="length" class="len-study"><h2>{label('いちばん上')}の長さ<small>{len(ld['words'])}社</small></h2>
  <div class="len-sum"><span>最短<b>{lo}</b>字</span><span>中央値<b>{round(ld['med'])}</b>字</span><span>平均<b>{round(ld['avg'])}</b>字</span><span>最長<b>{hi}</b>字</span></div>
  {strip_html(ld, '../', big=True)}
  <div class="filters len-bins">{bin_btns}</div>
  <div class="sorter" role="group" aria-label="並べ替え"><button type="button" data-sort="asc" aria-pressed="true">短い順</button><button type="button" data-sort="desc" aria-pressed="false">長い順</button></div>
  <ol class="len-list">{''.join(rows)}</ol>
</section>"""
    body = f"""<div class="page-head"><h1>統計</h1></div>
<div class="study">
<section id="names"><h2>呼び名<small>{label('いちばん上')}の呼び名　{len(stats['tops'])}社</small></h2>
  <div class="bars">{name_bars}</div></section>
<section id="tokens"><h2>よく使われる語<small>使っている会社の数</small></h2>
  <div class="bars">{tok_bars}</div>
  <div class="cloud">{cloud}</div></section>
{length_sec}
</div>"""
    write("topics/", page("topics/", "統計", body, current="topics/", desc="会社が掲げる言葉を数えて見えた傾向。呼び名、よく使われる語、言葉の長さ。"))


# ---------- 言語史 ----------
def build_history(C, W):
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
    write("history/", page("history/", "言語史", body, current="history/", noindex=not SITE["show_history"], desc="会社が掲げる言葉を改めた記録。古い言葉と新しい言葉を並べています。"))
    return len(pairs)


# ---------- 研究ノート ----------
def word_card(w, comment, rel):
    """研究ノートの :::word ID の札。言葉を紙の地に明朝で掲げ、社名・呼び名を添える"""
    if not w:
        return ""
    c = w["co"]
    note = f'<p class="wc-note">{esc(comment)}</p>' if comment else ""
    return (f'<figure class="wordcard"><a class="wc-body" href="{rel}{c["url"]}#{w["ID"]}">'
            f'<span class="wc-w">{esc(w["言葉"])}</span>'
            f'<span class="wc-who">{esc(c["会社名"])}<span class="chip">{esc(w["会社での呼び名"])}</span></span></a>'
            f'{note}</figure>')


def link_html(text, href):
    if re.match(r"https?://", href) and not href.startswith(BASE):
        return f'<a href="{href}" rel="noopener" target="_blank">{text}</a>'
    return f'<a href="{href}">{text}</a>'


def md_to_html(md, byid=None, rel="../../"):
    out, para, lst = [], [], None
    byid = byid or {}
    block = None

    def inline(s):
        s = esc(s, quote=False)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: link_html(m.group(1), m.group(2)), s)
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
        m = re.match(r"^:::word\s+(W\d+)\s*$", s)
        if m:
            flush()
            block = [m.group(1), []]
            continue
        if block is not None:
            if s == ":::":
                w = byid.get(block[0])
                if not w:
                    print(f"注意: 研究ノートの :::word {block[0]} が公開データにない")
                out.append(word_card(w, " ".join(block[1]).strip(), rel))
                block = None
            else:
                block[1].append(s.strip())
            continue
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


def build_notes(notes, W, og_jobs):
    if not notes:
        return
    byid = {w["ID"]: w for w in W}
    lis = "".join(f'<li><a href="{n["slug"]}/"><span class="t">{esc(n.get("題", n["slug"]))}</span><span class="d">{esc(n.get("日付", ""))}</span><span class="desc">{esc(n.get("説明", ""))}</span></a></li>' for n in notes)
    write("notes/", page("notes/", "研究ノート", f'<div class="page-head"><h1>研究ノート</h1><div class="count"><b>{len(notes)}</b>本</div></div><ul class="note-list">{lis}</ul>', current="notes/", desc="会社が掲げる言葉を読み比べる、会社のことば研究所の研究ノート。"))
    for n in notes:
        path = f"notes/{n['slug']}/"
        others = [x for x in notes if x is not n][:3]
        more = "".join(f'<li><a href="../{x["slug"]}/"><span class="t">{esc(x.get("題", ""))}</span><span class="d">{esc(x.get("日付", ""))}</span></a></li>' for x in others)
        more_html = f'<section class="sec"><p class="label">ほかの研究ノート</p><ul class="note-list">{more}</ul></section>' if more else ""
        body = f"""<nav class="crumbs" aria-label="現在地"><a href="../../">{esc(CFG['name'])}</a> › <a href="../">研究ノート</a></nav>
<div class="page-head"><h1>{esc(n.get('題', ''))}</h1><p class="byline">{esc(n.get('日付', ''))}　{esc(CFG['operator'])}</p></div>
<article class="prose">{md_to_html(n['body'], byid)}</article>
<section class="sec">{share_row(path, n.get('題', ''), 'note/' + n['slug'])}</section>
{more_html}"""
        og = f"og/notes/{n['slug']}.png"
        og_jobs.append({"out": og, "kind": "note", "title": n.get("題", "")})
        jsonld = {"@context": "https://schema.org", "@type": "Article", "headline": n.get("題", ""), "description": n.get("説明", ""),
                  "datePublished": n.get("日付", ""), "dateModified": n.get("更新") or n.get("日付", ""),
                  "author": {"@type": "Person", "name": CFG["operator"], "url": CFG["operator_url"]},
                  "publisher": {"@type": "Organization", "name": CFG["name"], "url": BASE},
                  "image": BASE + og, "mainEntityOfPage": BASE + path}
        write(path, page(path, n.get("題", ""), body, current="notes/", desc=n.get("説明"), og=og, jsonld=jsonld))


# ---------- この研究所について ----------
def build_about():
    sisters = "、".join(ext(u, esc(n), "sister/" + k) for n, u, k in SISTERS)
    body = f"""<div class="page-head"><h1>この研究所について</h1></div>
<article class="prose">
<h2>集め方</h2>
<ol class="steps">
  <li>有価証券報告書の「経営方針」の欄、会社の公式サイト、公式の発表から言葉を探す</li>
  <li>言葉を原文どおりに写す（全角・半角や記号も変えない）</li>
  <li>出典をもう一度開き、一字一句照らしてから載せる</li>
  <li>載せたあとも理念のページを見直し、言葉が改められたら古い言葉を残して新しい言葉を足す</li>
</ol>
<p>集めて照らす作業は AI（Claude）が行い、方針を決めて見直すのは運営者です。</p>
<h2>ことばの層</h2>
<p><strong>{label('いちばん上')}</strong>　ミッション、パーパス、経営理念、綱領など、会社の言葉の頂点にあるもの<br>
<strong>{label('目指す姿')}</strong>　ビジョン<br>
<strong>{label('価値観')}</strong>　バリュー、行動指針、社是・社訓など、短い項目が並ぶもの</p>
<h2>訂正・取り下げ</h2>
<p>誤りや新しい言葉に気づいたら、{ext(contact_url(), '訂正・ご意見のフォーム', 'contact/about')}からお知らせください。出典で確かめたうえで直します。</p>
<h2>運営</h2>
<p>{ext(CFG['operator_url'], esc(CFG['operator']), 'operator/about')}（コミュニティ研究家・キャリア研究家）。{sisters}も運営しています。</p>
</article>"""
    write("about/", page("about/", "この研究所について", body, current="about/", desc="会社のことば研究所の集め方と、ことばの層。"))


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
    # 長さは1社1点：その会社の北極星（複数あれば最初のもの）。英字が主の言葉は字数で比べられないので別に数える
    first_top = OrderedDict()
    for w in tops:
        first_top.setdefault(w["co"]["ID"], w)
    length_words = [w for w in first_top.values() if not w["latin"]]
    latin_tops = [w for w in first_top.values() if w["latin"]]
    return {"tops": tops, "names": names, "tokens": ranked, "token_map": token_map, "token_df": token_df,
            "length_words": length_words, "latin_tops": latin_tops,
            "changes": sum(1 for w in W if w["前の言葉のID"])}


def build_misc(C, W, token_pages, notes, og_jobs):
    urls = ["", "words/", "topics/", "about/"] + [c["url"] for c in C.values()] + list(token_pages.values())
    if SITE["show_history"]:
        urls.append("history/")
    if notes:
        urls += ["notes/"] + [f"notes/{n['slug']}/" for n in notes]
    sm = "".join(f"<url><loc>{esc(BASE + u)}</loc></url>" for u in urls)
    open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8").write(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>')
    # AI の学習用のクローラーだけを断る（ほかの3サイトと同じ）。検索用のクローラーとふつうの検索エンジンは通す
    blocks = "".join(f"User-agent: {b}\nDisallow: /\n\n" for b in AI_TRAINING)
    open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8").write(f"{blocks}User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n")
    json.dump([c["url"] for c in C.values()], open(os.path.join(OUT, "pick.json"), "w", encoding="utf-8"))
    pub = [{k: w[k] for k in WORD_COLS} for w in W]
    json.dump({"updated": TODAY.isoformat(), "count": len(pub), "words": pub}, open(os.path.join(OUT, "words.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for name in ("linkcheck.json", "stats.json"):
        src = os.path.join(ROOT, "data", name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(OUT, name))
    write("404.html", page("404.html", "見つかりません", '<div class="page-head"><h1>見つかりません</h1></div><p class="center"><a href="/">トップへ</a>　<a href="/words/">ことばを探す</a></p>', noindex=True))
    og_jobs.append({"out": "og/site.png", "kind": "site", "title": CFG["name"], "subtitle": CFG["subtitle"]})
    os.makedirs(os.path.join(OUT, "og"), exist_ok=True)
    json.dump(og_jobs, open(os.path.join(OUT, "og", "jobs.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
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
    stats = compute_stats(C, W)
    SITE["notes_exist"] = bool(notes)
    SITE["show_history"] = stats["changes"] >= HISTORY_MIN
    og_jobs = []
    build_top(C, W, stats)
    ids = list(C.keys())
    for c in C.values():
        build_company(c, C, ids, stats["token_df"], og_jobs)
    token_pages = build_token_pages(C, W, stats["token_map"])
    build_words(C, W, stats, token_pages)
    build_topics(C, W, stats, token_pages)
    build_history(C, W)
    build_notes(notes, W, og_jobs)
    build_about()
    build_misc(C, W, token_pages, notes, og_jobs)
    print(f"会社 {len(C)}　言葉 {len(W)}　改定 {stats['changes']}（言語史をメニューに出す: {SITE['show_history']}）　語のページ {len(token_pages)}　研究ノート {len(notes)}　ひらがな検索: {'あり' if KKS else 'なし'}")
    print("よく使われる語:", ", ".join(f"{t}({n})" for t, n in stats["tokens"][:12]))


if __name__ == "__main__":
    main()
