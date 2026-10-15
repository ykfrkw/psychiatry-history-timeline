"""
Purpose: 公開サイト一式（GitHub Pages にそのまま置ける静的ファイル）を作る。年表の A3 HTML を画面用の入口から見せ、
         PDF・プレビュー画像・表示した項目だけの CSV・ライセンス・README を添える
Inputs:  build.py が作った out/ の A3 HTML と PDF、profile dict、紙面に出た項目の id、元の events CSV
Outputs: <site>/index.html, timeline.html, psychiatry-history-timeline_{A3,A4x2}.pdf, preview.png,
         data/events.csv, LICENSE.txt, README.md
Depends: 標準ライブラリ（csv, html, shutil, subprocess, tempfile）。プレビュー画像に macOS の qlmanage（無ければ sips）
"""
import csv
import html
import shutil
import subprocess
import tempfile
from pathlib import Path

INDEX_TEMPLATE_PATH = Path(__file__).resolve().parent / "site_index.html"
SITE_FILE_STEM = "psychiatry-history-timeline"
PREVIEW_WIDTH_PX = 2400
PREVIEW_TIMEOUT_SEC = 120
CSV_ENCODING = "utf-8-sig"  # Excel で開いても文字化けしないよう BOM 付きで書く
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/legalcode.ja"
AUTHOR = "Furukawa Y"
FIRST_PUBLISHED_YEAR = 2026
DEFAULT_SITE_URL = "https://ykfrkw.github.io/psychiatry-history-timeline/"
SITE_DESCRIPTION = ("古代から現在までの精神医学の歩みを、制度・社会・診断・精神療法・身体療法の 6 列で見開きにまとめた縦組みの年表です。"
                    "A3 1 枚（または A4 2 枚）に印刷でき、右端の空欄の列に医局や病院の沿革を書き込めます。")


def credit_line(profile: dict, site_url: str) -> str:
    return f"「{profile['title']}」{AUTHOR}, CC BY 4.0, {site_url}"


def render_index(profile: dict, built_on: str, event_count: int, site_url: str) -> str:
    values = {
        "title": profile["title"], "description": SITE_DESCRIPTION, "footer_note": profile["footer_note"],
        "blog_url": profile["blog_url"] or "#", "credit": credit_line(profile, site_url), "built_on": built_on,
        "event_count": str(event_count), "pdf_a3": f"{SITE_FILE_STEM}_A3.pdf", "pdf_a4x2": f"{SITE_FILE_STEM}_A4x2.pdf",
    }
    page = INDEX_TEMPLATE_PATH.read_text(encoding="utf-8")
    for key, value in values.items():
        page = page.replace("{{" + key + "}}", html.escape(value, quote=True))
    return page


def write_shown_events(events_csv: Path, shown_ids: set[str], output_path: Path) -> int:
    """紙面に出た行だけを、元の列のまま書き出す。Return 書いた行数。"""
    with events_csv.open(encoding=CSV_ENCODING, newline="") as source:
        reader = csv.reader(source)
        header = next(reader, [])
        id_index = header.index("id")
        rows = [row for row in reader if len(row) > id_index and row[id_index].strip() in shown_ids]
    with output_path.open("w", encoding=CSV_ENCODING, newline="") as target:
        writer = csv.writer(target)
        writer.writerow(header)
        writer.writerows(rows)
    return len(rows)


def make_preview(pdf_path: Path, png_path: Path) -> bool:
    """PDF 1 ページ目の PNG。qlmanage は指定の大きさで描き直すので、72dpi から拡大する sips より鮮明。"""
    with tempfile.TemporaryDirectory() as work_dir:
        result = subprocess.run(["qlmanage", "-t", "-s", str(PREVIEW_WIDTH_PX), "-o", work_dir, str(pdf_path)],
                                capture_output=True, timeout=PREVIEW_TIMEOUT_SEC)
        rendered = Path(work_dir) / f"{pdf_path.name}.png"
        if result.returncode == 0 and rendered.exists():
            shutil.move(str(rendered), png_path)
            return True
    result = subprocess.run(["sips", "-s", "format", "png", "--resampleWidth", str(PREVIEW_WIDTH_PX),
                             str(pdf_path), "--out", str(png_path)], capture_output=True, timeout=PREVIEW_TIMEOUT_SEC)
    return result.returncode == 0 and png_path.exists()


def license_text(profile: dict, site_url: str) -> str:
    return f"""{profile['title']}（年表）
© {FIRST_PUBLISHED_YEAR} {AUTHOR}

この年表（PDF・HTML・data/events.csv）は、クリエイティブ・コモンズ 表示 4.0 国際（CC BY 4.0）で提供します。

要約（法的な条文ではありません。正式には全文を参照してください）
- 共有: どのような媒体・形式でも、複製・再配布できます
- 翻案: 改変・加筆・一部の抜き出しができます（医局版・講義資料など）
- 営利目的を含め、どのような目的でも利用できます
- 条件: 適切なクレジットを表示し、ライセンスへのリンクを示し、改変した場合はその旨を示してください

クレジット表記の例
  {credit_line(profile, site_url)}
  （改変した場合）{credit_line(profile, site_url)} をもとに○○が改変

全文: {LICENSE_URL}

各項目の出典は data/events.csv の source 列、HTML 版では各項目にマウスを重ねると表示されます。
誤りに気づいた場合は、ブログ（{profile['blog_url'] or site_url}）から知らせてください。
"""


def readme_text(profile: dict, site_url: str, built_on: str) -> str:
    return f"""# {profile['title']}（年表）

最新版: {site_url}　／　最終更新: {built_on}

## 使い方

- `{SITE_FILE_STEM}_A3.pdf` を A3 横で印刷します（拡大縮小なし・「実際のサイズ」で）
- A3 が無ければ `{SITE_FILE_STEM}_A4x2.pdf` を A4 縦で 2 枚印刷し、左右を貼り合わせて見開きにします
- 右端の空欄の列には、医局・病院・学会などの沿革を手書きで書き込めます（見出しも空欄です）。
  破線と小さな年（1900・1945・1995）は、左の列とおおよそ同じ高さの目安です
- `index.html` をブラウザで開くと、画面で拡大して読めます。各項目にマウスを重ねると補足と出典が出ます
- `data/events.csv` は紙面に載っている項目だけのデータです（列の意味は GitHub リポジトリの README を参照）

## 医局版（空欄の列を印字する版）の作り方

GitHub リポジトリの README「医局版の作り方」の手順に従い、医局の沿革を CSV に書いて
`python3 build.py profiles/<医局名>.toml` で作ります。

## ライセンス

CC BY 4.0（`LICENSE.txt`）。クレジット表記の例: {credit_line(profile, site_url)}
"""


def build_site(site_dir: Path, profile: dict, outputs: dict, shown_ids: set[str], events_csv: Path,
               built_on: str) -> list[Path]:
    """Return 作ったファイルの一覧。outputs は {"A3_html", "A3_pdf", "A4x2_pdf"} → Path。"""
    site_url = profile.get("site_url") or DEFAULT_SITE_URL
    missing = [name for name in ("A3_html", "A3_pdf", "A4x2_pdf") if not outputs.get(name)]
    if missing:
        raise SystemExit(f"公開サイトに必要な出力が無い: {missing}（Chrome が要る）")
    (site_dir / "data").mkdir(parents=True, exist_ok=True)
    written = []
    copies = {
        outputs["A3_html"]: site_dir / "timeline.html",
        outputs["A3_pdf"]: site_dir / f"{SITE_FILE_STEM}_A3.pdf",
        outputs["A4x2_pdf"]: site_dir / f"{SITE_FILE_STEM}_A4x2.pdf",
    }
    for source, target in copies.items():
        shutil.copyfile(source, target)
        written.append(target)
    preview_path = site_dir / "preview.png"
    if make_preview(copies[outputs["A3_pdf"]], preview_path):
        written.append(preview_path)
    else:
        print("警告: preview.png を作れなかった（qlmanage / sips）")
    csv_path = site_dir / "data" / "events.csv"
    row_count = write_shown_events(events_csv, shown_ids, csv_path)
    texts = {
        site_dir / "index.html": render_index(profile, built_on, row_count, site_url),
        site_dir / "LICENSE.txt": license_text(profile, site_url),
        site_dir / "README.md": readme_text(profile, site_url, built_on),
    }
    for path, text in texts.items():
        path.write_text(text, encoding="utf-8")
    written += [csv_path, *texts]
    return written
