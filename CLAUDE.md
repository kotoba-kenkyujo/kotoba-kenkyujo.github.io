# 会社のことば研究所：Claude Code 向けの引き継ぎ

https://kotoba-kenkyujo.github.io/ のリポジトリ。会社が掲げる言葉（ミッション、パーパス、社是、行動指針など）と、その移り変わりを記録するサイト。運営は黒田悠介さん。象徴の絵文字は「📢」（ファビコン・ロゴ）。

データ集めと公開判定は Claude の定期実行（このMacの scheduled task `kotoba-kenkyujo-data-run`、スキル `kotoba-kenkyujo-data`）が担当し、このリポジトリのコードは Claude Code が担当する。姉妹サイトは「コミュニティ図鑑」（~/Documents/community-zukan.github.io）と「あしたの転機観測所」。迷ったら図鑑の実装を読む。

## 流れ

1. Googleスプレッドシート「会社のことば研究所 データベース」（`1LF8Jgn_4ReXdWJowe--ViK-iYxFTzcPQBjshSPuKM7A`）の `言葉一覧` と `会社一覧` に、定期実行が言葉を集める。
2. 確認状況が「確認済み」の言葉だけが `公開用` タブに、会社は `公開用_会社` タブに QUERY で出る。
3. GitHub Actions「サイトを更新」が、毎日 5:50（日本時間）と main への push のときに、2つのタブをウェブに公開したCSVを読んで `build.py` でサイトを作り、`tools/make_og.py` で共有画像を作り、`tools/check_site.py` で点検してから GitHub Pages に出す。CSVのURLは config/site.json（空なら data/ の写しで作る）。actions の版は SHA で固定、権限は作る側と公開する側で分けている（図鑑・観測所と同じ）。
4. 毎週月曜：6:50「リンク切れの点検」（tools/check_links.py → data/linkcheck.json、要確認は Issue）、8:10「週次の数字」（tools/fetch_stats.py → data/stats.json。Secrets の GOATCOUNTER_API_KEY）、9:40ごろ このMacの scheduled task `kotoba-kenkyujo-weekly-report` が黒田さんに報告する。

Claude Code はシートの言葉を書き換えない。列を足すなどの変更が要るときは黒田さんに伝える。

## 守ること

- 補足の文は置かず、UI（数・札・注番号・印）で語る（2026/11/08 黒田さんの方針）。
- 言葉は原文どおりに出す。出典の注番号と確認日（✓）を必ず添える。
- 縦書きは明朝（Shippori Mincho B1）。朱色（--shu）は落款と「改定」の札だけ。
- 色・余白はデザインシステム「黒田悠介」（図鑑・観測所と同じ値）。assets/style.css の :root。
- 手元の Python は 3.9。f-string の {} の中にバックスラッシュを書かない。
- 層の表示は「北極星」（データは いちばん上）・「理想像」（目指す姿）・「価値観」。シートとスキルの値は変えず、build.py の LAYER_LABEL で読み替える（2026/11/08）。
- 呼び名は、4字までの漢字なら落款（.seal）、それ以外は朱の縦書き1行（.seal-line）。英字が主の言葉は縦にせず横書き（.yoko）。
- 掛け軸・今日のことば・共有画像の縦書きは、BudouX で文節に区切り、文節の途中で改行しない（build.py の phrases()、CSS の word-break: keep-all。2026/11/08）。
- 外へのテキストリンクは ext() で作る（新しいタブ・↗・GoatCounter のクリック記録）。
- 言語史は公開中の改定が HISTORY_MIN（5）件になるまで、メニュー・フッター・サイトマップに出さない（ページはある）。
- 明るい／暗い表示：最初は明るい表示（2026/11/08 黒田さん）、フッターのボタンで切り替え、localStorage の kotoba-theme に覚える。色は :root[data-theme="dark"] で上書き。
- robots.txt で AI の学習用クローラー（AI_TRAINING）を断る。検索エンジンは通す。

## ファイル

| ファイル | 中身 |
|---|---|
| build.py | サイトを作る（標準ライブラリだけ）。`python3 build.py --words testdata/words.csv --companies testdata/companies.csv` で手元のCSVから作る（data/ は書き換えない） |
| config/site.json | サイト名、CSVのURL、運営者、GoatCounter、Search Console の確認タグ（トップだけに出す）、訂正フォーム（contact_url と、会社名を事前入力する contact_target_entry）、searched_words（検索の例に混ぜる語） |
| assets/ | style.css、site.js（メニュー・表示の切り替え・リンクのコピー・ことばくじ・長さの図）、find.js（ことばを探す。言い換え表・検索の記録）、count.js（GoatCounter）、ファビコン（Noto Emoji の 📢。tools/emoji/） |
| config/synonyms.json | 検索の言い換え表（同じ仲間の語を1行に） |
| tools/make_og.py | 共有画像（1200×630）。build.py が書く _site/og/jobs.json を読む。Pillow と明朝体（tools/fonts/ に取ってくる）。手元では `.venv/bin/python tools/make_og.py`（.venv に pillow・pykakasi・budoux を入れてある。gitignore 済み） |
| tools/check_site.py・check_links.py・fetch_stats.py | 公開前の点検・出典URLの点検・GoatCounter の数字 |
| notes/ | 研究ノートの原稿（<スラッグ>.md。先頭に `---` で 題・日付・説明・公開。本文に `:::word ID` で言葉の札）。書き方は notes/_guide.md、テーマは notes/_themes.md。毎日 10:30 ごろ、このMacの scheduled task `kotoba-kenkyujo-notes` が1本書いて公開する |
| data/ | 最後に読んだ公開データの写し（Actions が更新する） |
| testdata/ | 手元で試すデータ（未確認の言葉も入っている。公開しない） |
| _design/ | 見本（2026/11/08。トップは案B「所報」、会社のページは案A「掛け軸と年表」を、補足の文を削った版 top-b2・company-a2 で採用） |
| 訂正フォーム | Googleフォーム「会社のことば研究所 訂正・ご意見」（1ySU7B6It0A-HuQojPAhQY0rmVr9ZVHFNUCGqvOv25tY）。回答はデータベースの `連絡フォーム` タブに入る |
| docs/collection-design.md | 情報収集の設計メモ |
| tools/skill/ | データ収集スキルの写し（本体は黒田さんのアカウントのスキル） |

## ページ

| URL | 中身 |
|---|---|
| / | 所報：収蔵の数（社・語）・今日のことば（北極星から日替わり。英字が主の言葉は横書き）・新収蔵・統計の小さなまとめ（北極星の長さは最短・平均・最長の数だけ）・出典の注 |
| /c/{会社ID}/ | 掛け軸（北極星）→ 理想像 → 価値観（呼び名ごと）→ 言語史 → 出典と訂正のリンク → 近い言葉 → 共有（X・Facebook・Threads・コピー）→ 前後の会社と🎲 |
| /words/ | ことばを探す（語と層で絞る。?q=） |
| /w/{語}/ | その語を含む言葉（2社以上が使う語だけ）。フォルダ名は日本語のまま |
| /topics/ | 統計：呼び名、よく使われる語、言葉の長さ（点の図・幅で絞る・並べ替え・全社の一覧。英字が主の言葉は別に数える） |
| /history/ | 言語史（前の言葉のIDでつながった改定） |
| /notes/ | 研究ノート |
| /about/ | 集め方（AIが集めて確かめ、運営が方針を決めて見直す）・ことばの層・訂正・取り下げ・運営（姉妹サイト3つ） |
