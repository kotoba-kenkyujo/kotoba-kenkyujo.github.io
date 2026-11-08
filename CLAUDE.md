# 会社のことば研究所：Claude Code 向けの引き継ぎ

https://kotoba-kenkyujo.github.io/ のリポジトリ。会社が掲げる言葉（ミッション、パーパス、社是、行動指針など）と、その移り変わりを記録するサイト。運営は黒田悠介さん。象徴の絵文字は「📢」（ファビコン・ロゴ）。

データ集めと公開判定は Claude の定期実行（このMacの scheduled task `kotoba-kenkyujo-data-run`、スキル `kotoba-kenkyujo-data`）が担当し、このリポジトリのコードは Claude Code が担当する。姉妹サイトは「コミュニティ図鑑」（~/Documents/community-zukan.github.io）と「あしたの転機観測所」。迷ったら図鑑の実装を読む。

## 流れ

1. Googleスプレッドシート「会社のことば研究所 データベース」（`1LF8Jgn_4ReXdWJowe--ViK-iYxFTzcPQBjshSPuKM7A`）の `言葉一覧` と `会社一覧` に、定期実行が言葉を集める。
2. 確認状況が「確認済み」の言葉だけが `公開用` タブに、会社は `公開用_会社` タブに QUERY で出る。
3. GitHub Actions「サイトを更新」が、毎日 5:50（日本時間）と main への push のときに、2つのタブをウェブに公開したCSVを読んで `build.py` でサイトを作り、GitHub Pages に出す。CSVのURLは config/site.json（空なら data/ の写しで作る）。

Claude Code はシートの言葉を書き換えない。列を足すなどの変更が要るときは黒田さんに伝える。

## 守ること

- 補足の文は置かず、UI（数・札・注番号・印）で語る（2026/11/08 黒田さんの方針）。
- 言葉は原文どおりに出す。出典の注番号と確認日（✓）を必ず添える。
- 縦書きは明朝（Shippori Mincho B1）。朱色（--shu）は落款と「改定」の札だけ。
- 色・余白はデザインシステム「黒田悠介」（図鑑・観測所と同じ値）。assets/style.css の :root。
- 手元の Python は 3.9。f-string の {} の中にバックスラッシュを書かない。

## ファイル

| ファイル | 中身 |
|---|---|
| build.py | サイトを作る（標準ライブラリだけ）。`python3 build.py --words testdata/words.csv --companies testdata/companies.csv` で手元のCSVから作る（data/ は書き換えない） |
| config/site.json | サイト名、CSVのURL、運営者 |
| assets/ | style.css、site.js（メニュー・共有・ことばくじ）、find.js（ことばを探す）、ファビコン（Noto Emoji の 📢。tools/emoji/） |
| notes/ | 研究ノートの原稿（<スラッグ>.md。先頭に `---` で 題・日付・説明・公開）。1本もなければメニューに出さない |
| data/ | 最後に読んだ公開データの写し（Actions が更新する） |
| testdata/ | 手元で試すデータ（未確認の言葉も入っている。公開しない） |
| _design/ | 見本（2026/11/08。トップは案B「所報」、会社のページは案A「掛け軸と年表」を、補足の文を削った版 top-b2・company-a2 で採用） |
| docs/collection-design.md | 情報収集の設計メモ |
| tools/skill/ | データ収集スキルの写し（本体は黒田さんのアカウントのスキル） |

## ページ

| URL | 中身 |
|---|---|
| / | 所報：日付・収蔵の数（社・語・改定）・今日のことば（いちばん上の言葉から日替わり。英字が主の言葉は除く）・新収蔵・研究テーマの小さなグラフ・出典の注 |
| /c/{会社ID}/ | 掛け軸（いちばん上）→ ビジョン → 価値観（呼び名ごと）→ 言語史 → 出典 → 近い言葉 → 共有・訂正・ことばくじ |
| /words/ | ことばを探す（語と層で絞る。?q=） |
| /w/{語}/ | その語を含む言葉（2社以上が使う語だけ）。フォルダ名は日本語のまま |
| /topics/ | 研究テーマ：呼び名、よく使われる語、言葉の長さ、文末の形、価値観の項目数 |
| /history/ | 言語史（前の言葉のIDでつながった改定） |
| /notes/ | 研究ノート |
| /about/ | 集め方・層・数え方・訂正・運営 |
