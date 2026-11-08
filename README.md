# 📢 会社のことば研究所

会社が掲げる言葉と、その移り変わりの記録。
https://kotoba-kenkyujo.github.io/

日本の会社が掲げるミッション・パーパス・社是・行動指針などの言葉を、有価証券報告書や公式サイトで一字一句確かめて収蔵しています。

## 手元で試す

```
python3 build.py --words testdata/words.csv --companies testdata/companies.csv
python3 -m http.server 8773 -d _site
```

運営：黒田悠介
