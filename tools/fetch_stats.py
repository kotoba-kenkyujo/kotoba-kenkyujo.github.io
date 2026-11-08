#!/usr/bin/env python3
"""GoatCounter の数字を読み、週次レポート用の data/stats.json を書く（毎週月曜の自動実行で使う）。
コミュニティ図鑑の tools/fetch_stats.py を研究所に合わせて写したもの（2026-11-08）。

  GOATCOUNTER_API_KEY=… python3 tools/fetch_stats.py

- 期間は日本時間の日付で区切る。「直近7日」は昨日までの7日間、「前の7日」はその前の7日間。
- 入れるもの：訪問数、会社のページ・研究ノート・統計の訪問数、上位20ページ・上位20の会社、
  検索語の上位20（結果あり search/〇〇 と 0件 search-zero/〇〇）、共有・ことばくじ・訂正フォーム・出典・長さの図などのクリック数。
- 個人を特定できる情報は入れない。GoatCounter もそれらを返さない。
- API キーがないときは何も書かずに終わる（終了コード0）。
"""
import datetime
import json
import os
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "stats.json")
API = "https://kotobakenkyujo.goatcounter.com/api/v0"
JST = datetime.timezone(datetime.timedelta(hours=9))
TOP = 20


def get(path, key, **params):
    url = API + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.load(res)
        except urllib.error.HTTPError as ex:
            if ex.code == 429 and attempt < 3:  # 呼びすぎ。少し待って試し直す
                time.sleep(5 * (attempt + 1))
                continue
            print("GoatCounter の API：%s → %s %s" % (path, ex.code, ex.read(300).decode("utf-8", "replace")), file=sys.stderr)
            raise


def iso(d):
    """日本時間のその日の0時を、UTC の時刻の文字列にする（GoatCounter は1時間単位）。"""
    return datetime.datetime(d.year, d.month, d.day, tzinfo=JST).astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def all_hits(key, start, end):
    """期間中のすべてのページ・イベントと、その訪問数。100件ずつ読む。"""
    hits, seen = [], []
    while True:
        params = {"start": start, "end": end, "limit": 100}
        if seen:
            params["exclude_paths"] = ",".join(str(i) for i in seen)
        data = get("/stats/hits", key, **params)
        page = data.get("hits") or []
        hits += page
        seen += [h["path_id"] for h in page]
        if not data.get("more") or not page:
            return hits
        time.sleep(1)


def summarize(key, first, last):
    """first〜last（日本時間の日付、両端を含む）の数字。"""
    start, end = iso(first), iso(last + datetime.timedelta(days=1))
    total = get("/stats/total", key, start=start, end=end)
    hits = all_hits(key, start, end)
    pages = sorted((h for h in hits if not h.get("event")), key=lambda h: -h["count"])
    events = [h for h in hits if h.get("event")]

    def ev(prefix):
        return sorted((h for h in events if h["path"].startswith(prefix)), key=lambda h: -h["count"])

    def words(prefix):
        return [{"word": h["path"][len(prefix):], "count": h["count"]} for h in ev(prefix)[:TOP]]

    def total_of(prefix):
        return sum(h["count"] for h in ev(prefix))

    def visits(prefix):
        return sum(h["count"] for h in pages if h["path"].startswith(prefix))

    companies = [h for h in pages if h["path"].startswith("/c/")]
    clicks = {}
    for name, prefix in [("共有", "share/"), ("ことばくじ", "pick/"), ("訂正・ご意見のフォーム", "contact/"),
                         ("出典を開く", "source/"), ("長さの図の点", "length-dot/"), ("長さの幅", "length-bin/"),
                         ("表示の切り替え", "theme/"), ("姉妹サイト", "sister/"), ("運営者", "operator/")]:
        clicks[name] = total_of(prefix)
    return {
        "start": first.isoformat(), "end": last.isoformat(),
        "visits": total.get("total", 0) - total.get("total_events", 0) if total.get("total_events") is not None else total.get("total", 0),
        "visits_including_events": total.get("total", 0),
        "key_numbers": {
            "company_page_visits": sum(h["count"] for h in companies),
            "searches": total_of("search/") + total_of("search-zero/"),
            "picks": total_of("pick/"),
        },
        "section_visits": {"ことばを探す": visits("/words/"), "語のページ": visits("/w/"), "統計": visits("/topics/"),
                           "言語史": visits("/history/"), "研究ノート": visits("/notes/"), "この研究所について": visits("/about/")},
        "top_pages": [{"path": h["path"], "title": h.get("title", ""), "count": h["count"]} for h in pages[:TOP]],
        "top_companies": [{"id": h["path"].strip("/").split("/")[-1], "title": h.get("title", ""), "count": h["count"]} for h in companies[:TOP]],
        "notes_visits": [{"path": h["path"], "count": h["count"]} for h in pages if h["path"].startswith("/notes/")],
        "search_words": words("search/"),
        "search_zero_words": words("search-zero/"),
        "clicks": clicks,
    }


def main():
    key = os.environ.get("GOATCOUNTER_API_KEY", "").strip()
    if not key:
        print("GOATCOUNTER_API_KEY がないので、stats.json は作りませんでした")
        return
    today = datetime.datetime.now(JST).date()
    last = today - datetime.timedelta(days=1)
    week = summarize(key, last - datetime.timedelta(days=6), last)
    prev = summarize(key, last - datetime.timedelta(days=13), last - datetime.timedelta(days=7))
    data = {"updated": datetime.datetime.now(JST).replace(microsecond=0).isoformat(),
            "note": "GoatCounter の訪問数（同じ人の同じページは1日1回）。期間は日本時間の日付で、両端を含む。visits はページの訪問数（クリックの記録を除く）。key_numbers は会社のページの訪問数・検索の数・ことばくじの数。GoatCounter の画面の Totals はクリックの記録も含む数で、visits_including_events と同じ。",
            "this_week": week, "previous_week": prev}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("stats.json：%s〜%s 訪問 %d（前の7日 %d）" % (week["start"], week["end"], week["visits"], prev["visits"]))


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as ex:
        print("GoatCounter の API でエラーになりました（%s）。キーの権限（Read statistics）を確かめてください" % ex.code, file=sys.stderr)
        sys.exit(1)
