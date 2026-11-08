"""EDINETから上場企業の有価証券報告書を取り、「経営方針」の欄から理念の言葉の候補を抜き出す。
使い方:
  python3 edinet_fetch.py <作業フォルダ> --from 2026-06-20 --to 2026-06-30 [--limit 20] [--known known.txt]
- APIキーは環境変数 EDINET_API_KEY、なければ macOS のキーチェーン（サービス名 EDINET_API_KEY）から読む。
  キーは画面にもファイルにも出さない。どちらにもなければ、理由を出して終了コード 2 で終える。
- 対象は書類種別 120（有価証券報告書）で、証券コードがある提出者（上場企業）だけ。
- --known を渡すと、そこに書かれた EDINETコード（1行に1つ、または prepare_run.py の known.txt の COMPANY 行）を飛ばす。
- 書き出すもの:
  edinet_candidates.json  会社ごとに 会社名・証券コード・EDINETコード・docID・決算期・提出日・書類URL・
                          経営方針の全文（policy）・理念らしい文（hits）
- hits は手がかりにすぎない。言葉を確定させるときは、policy の全文と公式サイトを読んで判断する。
"""
import json, os, re, subprocess, sys, csv, io, zipfile, datetime, time, urllib.request, urllib.parse

API = "https://api.edinet-fsa.go.jp/api/v2"
TAG = "jpcrp_cor:BusinessPolicyBusinessEnvironmentIssuesToAddressEtcTextBlock"
WORDS = ["理念", "パーパス", "Purpose", "PURPOSE", "ミッション", "Mission", "MISSION", "ビジョン", "Vision", "VISION",
         "使命", "存在意義", "社是", "社訓", "綱領", "バリュー", "Values", "VALUES", "行動指針", "フィロソフィー", "Way", "WAY", "志"]


def key():
    k = os.environ.get("EDINET_API_KEY", "").strip()
    if k:
        return k
    try:
        k = subprocess.run(["security", "find-generic-password", "-a", os.environ.get("USER", ""), "-s", "EDINET_API_KEY", "-w"],
                           capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        k = ""
    if not k:
        print("EDINETのAPIキーが見つからない（環境変数 EDINET_API_KEY も、キーチェーンの EDINET_API_KEY もない）。EDINETのチャネルは飛ばす。")
        sys.exit(2)
    return k


def get(url, params, k, binary=False):
    q = dict(params)
    q["Subscription-Key"] = k
    full = url + "?" + urllib.parse.urlencode(q)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(full, headers={"User-Agent": "kotoba-kenkyujo"}), timeout=60) as r:
                b = r.read()
            return b if binary else json.loads(b.decode("utf-8"))
        except Exception as e:
            err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"EDINETから取れない: {url.split('/')[-1]} {type(err).__name__}")


def policy_text(zbytes):
    z = zipfile.ZipFile(io.BytesIO(zbytes))
    for name in z.namelist():
        if "jpcrp" in name and name.endswith(".csv"):
            raw = z.read(name)
            for enc in ("utf-16", "utf-8-sig", "cp932"):
                try:
                    txt = raw.decode(enc)
                    break
                except Exception:
                    continue
            for row in csv.reader(io.StringIO(txt), delimiter="\t"):
                if row and row[0] == TAG:
                    t = re.sub(r"<[^>]+>", " ", row[-1])
                    return re.sub(r"[ \t　]+", " ", t).strip()
    return ""


def hits(text):
    out = []
    for s in re.split(r"(?<=。)", text):
        s = s.strip()
        if s and (any(w in s for w in WORDS) or re.search(r"[「『][^」』]{2,60}[」』]", s)):
            out.append(s[:300])
    return out[:12]


def main():
    a = sys.argv[1:]
    out = a[0]
    opt = {"--from": None, "--to": None, "--limit": "20", "--known": None}
    for o in opt:
        if o in a:
            opt[o] = a[a.index(o) + 1]
    os.makedirs(out, exist_ok=True)
    known = set()
    if opt["--known"] and os.path.exists(opt["--known"]):
        for line in open(opt["--known"], encoding="utf-8"):
            for m in re.findall(r"E\d{5}", line):
                known.add(m)
    k = key()
    d0 = datetime.date.fromisoformat(opt["--from"])
    d1 = datetime.date.fromisoformat(opt["--to"] or opt["--from"])
    docs = []
    d = d0
    while d <= d1:
        res = get(f"{API}/documents.json", {"date": d.isoformat(), "type": 2}, k).get("results") or []
        for x in res:
            if x.get("docTypeCode") == "120" and x.get("secCode") and x.get("edinetCode") not in known:
                docs.append(x)
        d += datetime.timedelta(days=1)
    seen, todo = set(), []
    for x in docs:
        if x["edinetCode"] not in seen:
            seen.add(x["edinetCode"])
            todo.append(x)
    todo = todo[: int(opt["--limit"])]
    result = []
    for x in todo:
        try:
            t = policy_text(get(f"{API}/documents/{x['docID']}", {"type": 5}, k, binary=True))
        except Exception as e:
            t = ""
            print("取れなかった:", x["filerName"], e)
        result.append({"会社名": x["filerName"], "証券コード": x["secCode"][:4], "EDINETコード": x["edinetCode"],
                       "docID": x["docID"], "決算期": x.get("periodEnd"), "提出日": (x.get("submitDateTime") or "")[:10],
                       "書類URL": f"https://disclosure2.edinet-fsa.go.jp/WZEK0040.aspx?{x['docID']}",
                       "policy": t, "hits": hits(t)})
        time.sleep(0.5)
    json.dump(result, open(os.path.join(out, "edinet_candidates.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"対象の有価証券報告書 {len(docs)} 件（既知を除く）、今回読んだ {len(result)} 社、経営方針が取れた {sum(1 for r in result if r['policy'])} 社")
    for r in result[:5]:
        print("-", r["会社名"], r["証券コード"], "hits", len(r["hits"]))


if __name__ == "__main__":
    main()
