"""SNSで共有したときの画像（1200×630）を作る。build.py が書いた _site/og/jobs.json を読み、_site/og/ に PNG を書く。

使い方: python tools/make_og.py   （Pillow が必要。書体は Shippori Mincho B1 を tools/fonts/ に取ってくる）
- サイト全体（og/site.png）：📢とサイト名と副題
- 会社のページ（og/c/<ID>.png）：その会社の北極星を、紙の地に明朝で掲げる。日本語は縦書き、英字が主の言葉は横書き
- 研究ノート（og/notes/<スラッグ>.png）：記事の題名と📢
画像の見た目を変えたら、build.py の VER は毎回変わるので、ブラウザやSNSの古い画像は時間がたてば入れ替わる。
"""
import json, os, sys, urllib.request
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_site")
FONTS = os.path.join(ROOT, "tools", "fonts")
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/shipporiminchob1/ShipporiMinchoB1-{}.ttf"
EMOJI = os.path.join(ROOT, "tools", "emoji", "megaphone-512.png")
W, H = 1200, 630
PAPER, LINE, INK, SUB, ROD, SHU, SKY = (251, 250, 246), (230, 225, 212), (26, 29, 35), (94, 99, 107), (42, 45, 51), (183, 53, 45), (24, 116, 184)
# 縦書きで向きを変える文字（句読点・括弧・長音）
VERT = {"、": "︑", "。": "︒", "，": "︐", "「": "﹁", "」": "﹂", "『": "﹃", "』": "﹄", "（": "︵", "）": "︶", "(": "︵", ")": "︶",
        "ー": "丨", "－": "丨", "-": "丨", "―": "丨", "〜": "≀", "～": "≀", "…": "︙", "：": "︓", "［": "﹇", "］": "﹈", "【": "︻", "】": "︼"}
try:  # 文節の途中で列を変えない（サイトと同じ BudouX）
    import budoux
    BUDOUX = budoux.load_default_japanese_parser()
except Exception:
    BUDOUX = None
HANG = "︑︒︐﹂﹄︶"
SMALL = set("ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ")


def font(weight, size):
    path = os.path.join(FONTS, f"ShipporiMinchoB1-{weight}.ttf")
    if not os.path.exists(path):
        os.makedirs(FONTS, exist_ok=True)
        print("書体を取ってくる:", weight)
        urllib.request.urlretrieve(FONT_URL.format(weight), path)
    return ImageFont.truetype(path, size)


def base():
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    d.rectangle([24, 24, W - 25, H - 25], outline=LINE, width=2)
    # 掛け軸の軸（上下）
    d.rounded_rectangle([0, 0, W, 14], radius=7, fill=ROD)
    d.rounded_rectangle([0, H - 14, W, H], radius=7, fill=ROD)
    return im, d


def emoji(size):
    return Image.open(EMOJI).convert("RGBA").resize((size, size), Image.LANCZOS)


def wrap(d, text, f, width):
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=f) > width and cur:
            # 句読点や閉じ括弧で行を始めない
            if ch in "、。」』）)・ー" and len(cur) > 1:
                lines.append(cur[:-1]); cur = cur[-1] + ch
            else:
                lines.append(cur); cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def wrap_words(d, text, f, width):
    lines, cur = [], ""
    for word in text.split(" "):
        t = (cur + " " + word).strip()
        if d.textlength(t, font=f) > width and cur:
            lines.append(cur); cur = word
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def columns(text, per_col):
    """縦書きの列に分ける。文節の途中では列を変えず、句読点・閉じ括弧は前の列の下にぶら下げる"""
    parts = BUDOUX.parse(text) if BUDOUX else list(text)
    cols, cur = [], []
    for part in parts:
        chars = [VERT.get(ch, ch) for ch in part]
        while chars:
            room = per_col - len(cur)
            body = [c for c in chars if c not in HANG]
            if len(body) <= room or (not cur and len(chars) > per_col):
                take = chars if len(body) <= room else chars[:per_col]
                cur += take
                chars = chars[len(take):]
            else:
                cols.append(cur)
                cur = []
        if len(cur) >= per_col and not (chars and chars[0] in HANG):
            cols.append(cur)
            cur = []
    if cur:
        cols.append(cur)
    return cols


def draw_vertical(d, text, right, left, top, bottom, size_max=72, size_min=26):
    """縦書き：右上から下へ、列は右から左へ。left より左にはみ出さない大きさを探す"""
    for size in range(size_max, size_min - 1, -2):
        step = int(size * 1.08)
        col_gap = int(size * 1.55)
        per_col = max(1, (bottom - top) // step)
        cols = columns(text, per_col)
        if right - size - (len(cols) - 1) * col_gap >= left:
            break
    f = font("ExtraBold", size)
    x = right - size
    for col in cols:
        y = top
        for ch in col:
            # 小さい「っ」などは、縦書きでは右上に寄せる
            dx = int(size * 0.12) if ch in SMALL else 0
            dy = -int(size * 0.12) if ch in SMALL else 0
            d.text((x + dx, y + dy), ch, font=f, fill=INK)
            y += step
        x -= col_gap
    return x


def wrap_mixed(d, text, f, width):
    """英字は単語で折り返し、それでも入らない行（日本語が混ざる行）は字で折り返す"""
    out = []
    for line in wrap_words(d, text, f, width):
        out += wrap(d, line, f, width) if d.textlength(line, font=f) > width else [line]
    return out


def site(job):
    im, d = base()
    im.paste(emoji(150), (90, 120), emoji(150))
    f = font("ExtraBold", 92)
    d.text((90, 300), job["title"], font=f, fill=INK)
    d.text((94, 430), job.get("subtitle", ""), font=font("Bold", 34), fill=SUB)
    return im


def note(job):
    im, d = base()
    im.paste(emoji(84), (90, 70), emoji(84))
    d.text((190, 92), "会社のことば研究所　研究ノート", font=font("Bold", 30), fill=SUB)
    f = font("ExtraBold", 64)
    lines = wrap(d, job["title"], f, W - 200)
    if len(lines) > 3:
        f = font("ExtraBold", 52)
        lines = wrap(d, job["title"], f, W - 200)[:4]
    y = 230
    for line in lines:
        d.text((90, y), line, font=f, fill=INK)
        y += int(f.size * 1.4)
    return im


def company(job):
    im, d = base()
    name = job["company"]
    # 右の帯：社名を縦書き、その下に呼び名（朱）
    fn = font("Bold", 34)
    x = W - 110
    y = 70
    for ch in name.replace("株式会社", "")[:12]:
        d.text((x, y), VERT.get(ch, ch), font=fn, fill=INK)
        y += 40
    fc = font("Bold", 26)
    y += 20
    for ch in job["name"][:10]:
        d.text((x + 4, y), VERT.get(ch, ch), font=fc, fill=SHU)
        y += 30
    # 左下に📢と研究所の名前
    im.paste(emoji(56), (70, H - 120), emoji(56))
    d.text((140, H - 108), "会社のことば研究所", font=font("Bold", 28), fill=SUB)
    if job.get("latin"):
        f = font("ExtraBold", 72)
        lines = wrap_mixed(d, job["word"], f, W - 360)
        if len(lines) > 3:
            f = font("ExtraBold", 54)
            lines = wrap_mixed(d, job["word"], f, W - 360)[:4]
        total = len(lines) * int(f.size * 1.3)
        y = (H - total) // 2 - 30
        for line in lines:
            d.text((90, y), line, font=f, fill=INK)
            y += int(f.size * 1.3)
    else:
        draw_vertical(d, job["word"], right=W - 190, left=420, top=64, bottom=H - 60)
    return im


def main():
    jobs_path = os.path.join(OUT, "og", "jobs.json")
    if not os.path.exists(jobs_path):
        sys.exit("先に build.py を実行する（_site/og/jobs.json がない）")
    jobs = json.load(open(jobs_path, encoding="utf-8"))
    makers = {"site": site, "note": note, "company": company}
    made = 0
    for job in jobs:
        out = os.path.join(OUT, job["out"])
        os.makedirs(os.path.dirname(out), exist_ok=True)
        try:
            makers[job["kind"]](job).save(out, optimize=True)
            made += 1
        except Exception as e:
            print("作れなかった:", job["out"], e)
    os.remove(jobs_path)
    print(f"共有画像を {made} 枚作りました")


if __name__ == "__main__":
    main()
