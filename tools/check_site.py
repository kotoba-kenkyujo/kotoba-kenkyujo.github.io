#!/usr/bin/env python3
"""作ったサイト（_site/）を公開の前に点検する（コミュニティ図鑑の点検を写したもの。2026-11-08）。

公開を止めるもの（終了コード1）：
- pick.json の会社すべてにページがあり、title が入っていること
- サイト内のリンク（href・src）の行き先のファイルがあること
- sitemap.xml のURLのページがあること
- words.json の言葉の数が0でないこと

公開は止めず、--report を付けたときに報告のファイルに書くもの（Actions が Issue にする）：
- 共有画像（og:image）のファイルがない（make_og.py が失敗したとき）
- h1 が1つでない・見出しの段が飛んでいる・画像に alt がない・同じ id が1ページに2つある

使い方：python3 tools/check_site.py [--report site-report.md] [_site のパス]
"""
import collections
import html.parser
import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARGS = sys.argv[1:]
REPORT = None
if "--report" in ARGS:
    i = ARGS.index("--report")
    REPORT = ARGS[i + 1]
    del ARGS[i:i + 2]
SITE = ARGS[0] if ARGS else os.path.join(ROOT, "_site")
MAX_SHOW = 30
BASE = json.load(open(os.path.join(ROOT, "config", "site.json"), encoding="utf-8"))["base_url"].rstrip("/") + "/"

problems = []
soft = collections.defaultdict(list)


class Outline(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.headings, self.ids, self.no_alt = [], [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append(int(tag[1]))
        if a.get("id"):
            self.ids.append(a["id"])
        if tag == "img" and "alt" not in a:
            self.no_alt += 1


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def soft_checks(text, rel):
    o = Outline()
    o.feed(text)
    h1 = o.headings.count(1)
    if h1 != 1 and not rel.endswith("404.html"):
        soft["h1 が1つでないページ"].append(f"{rel}（{h1}個）")
    for a, b in zip(o.headings, o.headings[1:]):
        if b > a + 1:
            soft["見出しの段が飛んでいるページ"].append(f"{rel}（h{a} の次が h{b}）")
            break
    dup = [i for i, n in collections.Counter(o.ids).items() if n > 1]
    if dup:
        soft["同じ id が2つ以上あるページ"].append(f"{rel}（{'、'.join(dup[:5])}）")
    if o.no_alt:
        soft["alt のない画像があるページ"].append(f"{rel}（{o.no_alt}枚）")


def unescape(s):
    return s.replace("&amp;", "&").replace("&quot;", '"').replace("&#x27;", "'")


def target_exists(page_dir, ref):
    """サイト内の参照の行き先があるか。外へのリンクや # だけのものは確かめない"""
    ref = unescape(ref)
    if ref.startswith(BASE):
        ref = "/" + ref[len(BASE):]
    if re.match(r"^[a-z]+:", ref) or ref.startswith("//") or ref.startswith("#") or not ref:
        return True
    path = urllib.parse.unquote(ref.split("#")[0].split("?")[0])
    if not path:
        return True
    full = os.path.join(SITE, path.lstrip("/")) if path.startswith("/") else os.path.normpath(os.path.join(page_dir, path))
    if os.path.isdir(full):
        full = os.path.join(full, "index.html")
    return os.path.exists(full)


def write_report():
    total = sum(len(v) for v in soft.values())
    if total:
        print(f"直したほうがよいところ（公開は止めない）：{total}件" + "".join(f"\n  {k} {len(v)}件" for k, v in soft.items()))
    if not REPORT:
        return
    if os.path.isfile(REPORT):
        os.remove(REPORT)
    if not total:
        return
    lines = [f"毎日の自動更新で、作ったサイトを点検しました。直したほうがよいところが {total}件ありました。サイトの公開は止めていません。", ""]
    for kind, rows in soft.items():
        lines += [f"## {kind}（{len(rows)}件）", ""]
        lines += ["- " + r for r in rows[:MAX_SHOW]]
        if len(rows) > MAX_SHOW:
            lines.append(f"- ほか {len(rows) - MAX_SHOW}件")
        lines.append("")
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    if not os.path.isdir(SITE):
        print(f"{SITE} がありません")
        return 1
    words = json.load(open(os.path.join(SITE, "words.json"), encoding="utf-8"))
    if not words.get("words"):
        problems.append("words.json に言葉が1つもない")
    pages = json.load(open(os.path.join(SITE, "pick.json"), encoding="utf-8"))

    for rel in pages:
        page = os.path.join(SITE, rel, "index.html")
        if not os.path.exists(page):
            problems.append(f"会社のページがない：{rel}")
            continue
        t = read(page)
        title = re.search(r"<title>([^<]*)</title>", t)
        if not title or not title.group(1).strip():
            problems.append(f"title が空：{rel}")

    broken = {}
    for dirpath, _, files in os.walk(SITE):
        for name in files:
            if not name.endswith(".html"):
                continue
            page = os.path.join(dirpath, name)
            rel = os.path.relpath(page, SITE)
            text = read(page)
            soft_checks(text, rel)
            og = re.search(r'<meta property="og:image" content="([^"]+)"', text)
            if og and not target_exists(dirpath, og.group(1)):
                soft["共有画像のファイルがないページ"].append(f"{rel}（{og.group(1)}）")
            for ref in re.findall(r'(?:href|src)="([^"]+)"', text):
                if not target_exists(dirpath, ref):
                    broken.setdefault(rel, set()).add(ref)
    for page, refs in sorted(broken.items()):
        for ref in sorted(refs)[:5]:
            problems.append(f"リンク先がない：{page} → {ref}")

    for url in re.findall(r"<loc>([^<]+)</loc>", read(os.path.join(SITE, "sitemap.xml"))):
        if not target_exists(SITE, url):
            problems.append(f"サイトマップのページがない：{url}")

    write_report()
    if problems:
        print(f"サイトの点検で {len(problems)}件の問題が見つかりました。公開を止めます。")
        for p in problems[:100]:
            print("  - " + p)
        return 1
    print(f"サイトの点検：会社のページ {len(pages)}件、言葉 {len(words['words'])}件。リンク・サイトマップに問題はありません。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
