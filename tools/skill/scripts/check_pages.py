"""点検用。理念ページを開き直し、確認済みの言葉がそのまま載っているかを確かめる。
使い方: python3 check_pages.py targets.json result.json
- targets.json は prepare_run.py が書き出す inspect.json（会社ごとに 会社ID・会社名・理念ページのURL・言葉の一覧）。
- ページの文字から空白と改行を除き、全角英数を半角にそろえてから、言葉が含まれるかを比べる。
- 結果（result.json）は会社ごとに 開けたか（HTTP の状態）と、言葉ごとの 見つかった／見つからない。
- 「見つからない」は改定の候補にすぎない。ページがJavaScriptで文字を出している、画像で載せている、
  といった理由でも見つからないことがあるので、必ずページを自分で読んで確かめる。
"""
import json, re, sys, unicodedata, urllib.request, html


def norm(s):
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", "", s)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (kotoba-kenkyujo check)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        cs = r.headers.get_content_charset() or "utf-8"
    try:
        t = raw.decode(cs, errors="replace")
    except LookupError:
        t = raw.decode("utf-8", errors="replace")
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return html.unescape(t)


def main():
    targets = json.load(open(sys.argv[1], encoding="utf-8"))
    out = []
    for t in targets:
        rec = {"会社ID": t["会社ID"], "会社名": t.get("会社名", ""), "URL": t["URL"], "状態": "", "言葉": []}
        try:
            page = norm(fetch(t["URL"]))
            rec["状態"] = "開けた"
        except Exception as e:
            page = ""
            rec["状態"] = f"開けない（{type(e).__name__}: {str(e)[:60]}）"
        for w in t["言葉"]:
            found = bool(page) and norm(w["言葉"]) in page
            rec["言葉"].append({"ID": w["ID"], "言葉": w["言葉"], "結果": "見つかった" if found else "見つからない"})
        out.append(rec)
        miss = sum(1 for w in rec["言葉"] if w["結果"] == "見つからない")
        print(f'{t["会社ID"]} {rec["会社名"]} {rec["状態"]} 見つからない {miss}/{len(rec["言葉"])}')
    json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
