"""定期実行の下ごしらえ。
使い方: python3 prepare_run.py <会社一覧の get_values 結果> <言葉一覧の get_values 結果> <除外リストの get_values 結果> <作業フォルダ> <今日 YYYY/MM/DD>
        [--pub-limit 20] [--inspect-limit 10] [--inspect-days 90]
- get_values の結果（{"range":..., "values":[[...]]}）を保存したファイルをそのまま渡す。範囲は 会社一覧!A:P、言葉一覧!A:U、除外リスト!A:E。
- known.txt には除外リストのEDINETコード（E列）も入るので、edinet_fetch.py --known に渡せば除外した会社も飛ばされる。
- 作業フォルダに次を書き出す:
  known.txt     既存の会社（COMPANY\tID\t会社名\t証券コード\tEDINETコード\tURL）と除外リスト（EXCL\t会社名\tURL）。重複照合とEDINETの既知の除外に使う
  pub.json      公開判定の対象（未確認の言葉を追加日が古い順に上限まで、会社ごとにまとめたもの）
  inspect.json  点検の対象（check_pages.py にそのまま渡せる形）
  status.json   件数・次のID・空いている行番号・重複などの集計
  check.py      表記チェックの写し
- 空白行・ID重複・会社の重複が出たら、先に直してから進む。
"""
import json, re, sys, os, shutil, collections, datetime

a = sys.argv[1:]
opt = {"--pub-limit": 20, "--inspect-limit": 10, "--inspect-days": 90}
for k in list(opt):
    if k in a:
        i = a.index(k); opt[k] = int(a[i + 1]); del a[i:i + 2]
cf, wf, ef, out, today = a[:5]
os.makedirs(out, exist_ok=True)
shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), "check.py"), os.path.join(out, "check.py"))
td = datetime.datetime.strptime(today, "%Y/%m/%d").date()


def load(f, n):
    v = json.load(open(f, encoding="utf-8")).get("values", [])
    return [r + [""] * (n - len(r)) for r in v[1:]]


def pdate(s):
    try:
        return datetime.datetime.strptime(s, "%Y/%m/%d").date()
    except Exception:
        return None


comp = load(cf, 16)   # A:ID B:会社名 C:読み D:証券コード E:EDINETコード F:業種 G:上場区分 H:設立年 I:公式サイト J:理念ページ K:確認日 L:確認状況 M:追加日 N:収集元 O:黒田メモ P:内部メモ
words = load(wf, 21)  # A:ID B:会社ID C:会社名 D:対象 E:層 F:呼び名 G:順番 H:言葉 I:英語版 J:使い始め K:使い終わり L:前のID M:出典URL N:種類 O:出典日 P:確認日 Q:確認状況 R:追加日 S:収集元 T:黒田メモ U:内部メモ
excl = load(ef, 5)   # A:会社名 B:URL C:理由 D:日付 E:EDINETコード

cblank = [i + 2 for i, r in enumerate(comp) if not r[0]]
wblank = [i + 2 for i, r in enumerate(words) if not r[0]]
cids = [r[0] for r in comp if r[0]]
wids = [r[0] for r in words if r[0]]
dup = {"会社ID": [k for k, v in collections.Counter(cids).items() if v > 1],
       "言葉ID": [k for k, v in collections.Counter(wids).items() if v > 1],
       "証券コード": [k for k, v in collections.Counter(r[3] for r in comp if r[3]).items() if v > 1],
       "会社名": [k for k, v in collections.Counter(r[1] for r in comp if r[1]).items() if v > 1]}


def nxt(ids, p, width):
    nums = [int(m.group(1)) for x in ids for m in [re.fullmatch(p + r"(\d+)", x)] if m]
    return f"{p}{(max(nums) if nums else 0) + 1:0{width}d}"


cname = {r[0]: r[1] for r in comp}
crow = {r[0]: r for r in comp}

unconf = sorted([r for r in words if r[16] == "未確認"], key=lambda r: (pdate(r[17]) or datetime.date.max, r[0]))[:opt["--pub-limit"]]
wpos = {r[0]: i + 2 for i, r in enumerate(words)}
pub = collections.OrderedDict()
for r in unconf:
    pub.setdefault(r[1], {"会社ID": r[1], "会社名": cname.get(r[1], ""), "言葉": []})["言葉"].append(
        {"行": wpos[r[0]], **{h: r[j] for j, h in enumerate(["ID", "会社ID", "会社名", "対象", "層", "呼び名", "順番", "言葉", "英語版", "使い始め", "使い終わり", "前のID", "出典URL", "出典の種類", "出典の日付", "確認日", "確認状況", "追加日", "収集元"])}, "内部メモ": r[20]})

# 点検：要更新の会社 → 確認日が古い会社の順
cur = collections.defaultdict(list)
for r in words:
    if r[16] == "確認済み" and not r[10]:
        cur[r[1]].append({"ID": r[0], "言葉": r[7]})
need = [r[0] for r in comp if r[11] == "要更新"]
old = sorted([r for r in comp if r[11] == "確認済み" and pdate(r[10]) and (td - pdate(r[10])).days >= opt["--inspect-days"]],
             key=lambda r: pdate(r[10]))
order = need + [r[0] for r in old if r[0] not in need]
inspect = [{"会社ID": c, "会社名": cname.get(c, ""), "URL": crow[c][9], "行": cids.index(c) + 2, "言葉": cur.get(c, [])}
           for c in order if c in crow and crow[c][9]][:opt["--inspect-limit"]]

with open(os.path.join(out, "known.txt"), "w", encoding="utf-8") as f:
    for r in comp:
        f.write(f"COMPANY\t{r[0]}\t{r[1]}\t{r[3]}\t{r[4]}\t{r[8]}\n")
    for r in excl:
        f.write(f"EXCL\t{r[0]}\t{r[1]}\t{r[4]}\n")
json.dump(list(pub.values()), open(os.path.join(out, "pub.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(inspect, open(os.path.join(out, "inspect.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
st = {"会社の件数": len(comp), "言葉の件数": len(words),
      "会社の確認状況": dict(collections.Counter(r[11] for r in comp)),
      "言葉の確認状況": dict(collections.Counter(r[16] for r in words)),
      "次の会社ID": nxt(cids, "C", 4), "次の言葉ID": nxt(wids, "W", 5),
      "会社一覧の次の行": len(comp) + 2, "言葉一覧の次の行": len(words) + 2, "除外リストの次の行": len(excl) + 2,
      "空白行": {"会社一覧": cblank, "言葉一覧": wblank}, "重複": dup,
      "公開判定の対象": [w["ID"] for c in pub.values() for w in c["言葉"]],
      "点検の対象": [x["会社ID"] for x in inspect]}
json.dump(st, open(os.path.join(out, "status.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for k, v in st.items():
    print(k, v if not isinstance(v, list) or len(v) < 12 else f"{len(v)}件 {v[:5]} ...")
