"""表記の機械チェック。書き込む前の行を通し、指摘を0件にしてから書く。
使い方: python3 check.py rows.json
- rows.json は行のリスト。各行は {"tab": "会社一覧" または "言葉一覧", "A": ..., "B": ..., ...}（書く列だけでよい）。
- 言葉一覧の「言葉」（H列）は原文どおりが決まりなので、字の種類や空白は指摘しない。長さと改行だけを見る。
"""
import json, re, sys

OPT = {
    "会社一覧": {"G": {"プライム", "スタンダード", "グロース", "名証・地方", "非上場", ""},
                 "L": {"未確認", "確認済み", "要更新", "非公開"},
                 "N": {"AI", "EDINET", "自分", "掲載依頼"}},
    "言葉一覧": {"D": {"会社全体", "事業部", "ブランド"},
                 "E": {"いちばん上", "目指す姿", "価値観"},
                 "N": {"公式サイト", "公式発表", "有価証券報告書", "統合報告書", "採用ページ"},
                 "Q": {"未確認", "確認済み", "要更新", "非公開"},
                 "S": {"AI", "EDINET", "自分", "掲載依頼"}},
}
DATE = re.compile(r"\d{4}/\d{2}/\d{2}")
MONTH = re.compile(r"\d{4}/\d{2}")
p = []
for r in json.load(open(sys.argv[1], encoding="utf-8")):
    tab, rid = r.get("tab"), r.get("A", "?")
    if tab not in OPT:
        p.append((rid, "tab", "tab は 会社一覧 か 言葉一覧", tab)); continue
    for col, ok in OPT[tab].items():
        if col in r and str(r[col]) not in ok:
            p.append((rid, col, "選択肢にない値", r[col]))
    if tab == "会社一覧":
        if not re.fullmatch(r"C\d{4}", str(rid)): p.append((rid, "A", "会社IDの形（C0001）", rid))
        if r.get("D") and not re.fullmatch(r"[0-9A-Z]{4}", str(r["D"])): p.append((rid, "D", "証券コードは4桁", r["D"]))
        if r.get("E") and not re.fullmatch(r"E\d{5}", str(r["E"])): p.append((rid, "E", "EDINETコードの形（E12345）", r["E"]))
        if r.get("H") and not re.fullmatch(r"\d{4}", str(r["H"])): p.append((rid, "H", "設立年は西暦4桁", r["H"]))
        for c in ("K", "M"):
            if r.get(c) and not DATE.fullmatch(str(r[c])): p.append((rid, c, "日付の形（2026/11/08）", r[c]))
        for c in ("I", "J"):
            if r.get(c) and not str(r[c]).startswith("http"): p.append((rid, c, "URLの形", r[c]))
        if "O" in r: p.append((rid, "O", "黒田メモにAIは書かない", ""))
    else:
        if not re.fullmatch(r"W\d{5}", str(rid)): p.append((rid, "A", "言葉IDの形（W00001）", rid))
        if r.get("B") is not None and not re.fullmatch(r"C\d{4}", str(r["B"])): p.append((rid, "B", "会社IDの形", r["B"]))
        if "C" in r: p.append((rid, "C", "会社名は数式の列なので書かない", ""))
        if "T" in r: p.append((rid, "T", "黒田メモにAIは書かない", ""))
        if "H" in r and not str(r["H"]).strip(): p.append((rid, "H", "言葉が空", ""))
        if r.get("H") and len(str(r["H"])) > 200: p.append((rid, "H", "言葉が長い。説明文を書き写していないか", len(str(r["H"]))))
        if r.get("E") == "価値観" and not r.get("G"): p.append((rid, "G", "価値観には項目の順番を書く", ""))
        if r.get("E") and r["E"] != "価値観" and r.get("G"): p.append((rid, "G", "項目の順番は価値観だけ", r["G"]))
        for c in ("J", "K"):
            if r.get(c) and not MONTH.fullmatch(str(r[c])): p.append((rid, c, "年月の形（2026/04）", r[c]))
        for c in ("O", "P", "R"):
            if r.get(c) and not DATE.fullmatch(str(r[c])) and not (c == "O" and MONTH.fullmatch(str(r[c]))):
                p.append((rid, c, "日付の形（2026/11/08。出典の日付は 2026/06 も可）", r[c]))
        if r.get("L") and not re.fullmatch(r"W\d{5}", str(r["L"])): p.append((rid, "L", "前の言葉のIDの形", r["L"]))
        if "M" in r and not str(r.get("M", "")).startswith("http"): p.append((rid, "M", "出典URLがない", r.get("M")))
        if r.get("Q") == "確認済み" and not r.get("P"): p.append((rid, "P", "確認済みなのに確認日が空", ""))
    for col, val in r.items():
        if col in ("tab", "H", "I"):
            continue
        s = str(val)
        if re.search(r"[｡-ﾟ]", s): p.append((rid, col, "半角カナ", s[:20]))
        if re.search(r"^\s|\s$|　", s): p.append((rid, col, "余分な空白", repr(s[:30])))
for x in p:
    print(*x, sep=" | ")
print("指摘", len(p), "件")
