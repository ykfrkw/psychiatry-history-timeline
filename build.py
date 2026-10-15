"""
Purpose: CSV の年表データから『情報の歴史』風の縦組み見開き年表（A3 横 1 枚 = A4 縦 × 2）を HTML/PDF に描画する
Inputs:  profile（profiles/*.toml）。そこに書かれた events / eras / local の CSV（data/）、template.css、timeline/fit.js
Outputs: out/timeline_<profile>_A3.html/.pdf（1 ページ）、out/timeline_<profile>_A4x2.html/.pdf（2 ページ）。
         --site <dir> を付けると、GitHub Pages に置く公開サイト一式も（timeline/site.py）
Depends: Python 3.11+ の標準ライブラリのみ。自動フィットの実行と PDF 化に Google Chrome（headless）。無ければ HTML のみ
Usage:   python3 build.py profiles/sample.toml
         python3 build.py profiles/public.toml --site site/
"""
import argparse
import datetime
import re
import subprocess
from pathlib import Path

from timeline.columns import build_columns
from timeline.data import LOCAL_TRACK, build_sections, load_eras, load_events, load_profile, select_events
from timeline.render import render_document
from timeline.site import build_site

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "out"
CSS_PATH = PROJECT_ROOT / "template.css"
FIT_JS_PATH = PROJECT_ROOT / "timeline" / "fit.js"
CHROME_PATH = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
CHROME_TIMEOUT_SEC = 180
# fit.js は同期で走るが、フォント読込の待ちを含めて余裕を持たせる
CHROME_VIRTUAL_TIME_MS = 5000
VARIANTS = ("A3", "A4x2")
PDF_PAGE_PATTERN = re.compile(rb"/Type\s*/Page(?![a-zA-Z])")
HTML_TAG_PATTERN = re.compile(r"<html[^>]*>")
FIT_ATTRIBUTE_PATTERN = re.compile(r'data-fit-([a-z-]+)="([^"]*)"')


def run_chrome(extra_args: list[str], html_path: Path) -> subprocess.CompletedProcess:
    command = [
        str(CHROME_PATH), "--headless", "--disable-gpu", "--no-pdf-header-footer",
        f"--virtual-time-budget={CHROME_VIRTUAL_TIME_MS}", *extra_args, html_path.as_uri(),
    ]
    return subprocess.run(command, capture_output=True, timeout=CHROME_TIMEOUT_SEC)


def read_fit_result(html_path: Path) -> dict:
    result = run_chrome(["--dump-dom"], html_path)
    root_tag = HTML_TAG_PATTERN.search(result.stdout.decode(errors="replace"))
    return dict(FIT_ATTRIBUTE_PATTERN.findall(root_tag.group(0))) if root_tag else {}


def print_to_pdf(html_path: Path, pdf_path: Path) -> bool:
    result = run_chrome([f"--print-to-pdf={pdf_path}"], html_path)
    if result.returncode != 0 or not pdf_path.exists():
        print(f"警告: PDF 化に失敗 {pdf_path.name}: {result.stderr.decode(errors='replace')[-300:]}")
        return False
    return True


def count_pdf_pages(pdf_path: Path) -> int:
    return len(PDF_PAGE_PATTERN.findall(pdf_path.read_bytes()))


def report_fit(fit: dict, events_by_id: dict) -> None:
    if not fit:
        print("警告: 自動フィットの結果を読めなかった（HTML のフッタ表示を確認すること）")
        return
    print(f"自動フィット: 本文 {fit.get('font')}pt・紙幅で非表示 {fit.get('hidden')} 件")
    for event_id in fit.get("hidden-ids", "").split():
        event = events_by_id.get(event_id)
        if event:
            print(f"  非表示: {event_id} {event.year_start} {event.title}（重要度 {event.importance}）")
    if float(fit.get("spread-over-mm", 0)) > 0:
        print(f"警告: 最小フォント・重要度 1 等のみでも版面が {fit['spread-over-mm']}mm 溢れる。項目を減らすこと")
    if float(fit.get("side-over-mm", 0)) > 0:
        print(f"警告: 左余白（古代箱）が {fit['side-over-mm']}mm 溢れる。ancient_cutoff か古代の項目を見直すこと")


def main(profile_arg: str, site_arg: str | None = None) -> None:
    profile_path = Path(profile_arg)
    if not profile_path.is_absolute():
        profile_path = (Path.cwd() / profile_path).resolve()
    if not profile_path.exists():
        raise SystemExit(f"profile が見つからない: {profile_arg}")
    profile = load_profile(profile_path)
    today = datetime.date.today()
    profile["current_year"] = today.year

    events, event_rows = load_events(PROJECT_ROOT / profile["events_csv"])
    local_rows = 0
    if profile["local_csv"]:
        local_events, local_rows = load_events(PROJECT_ROOT / profile["local_csv"], forced_track=LOCAL_TRACK)
        events += local_events
    eras = load_eras(PROJECT_ROOT / profile["eras_csv"])
    selected, filtered_count = select_events(events, profile)
    if not selected:
        raise SystemExit("表示できる項目が 0 件。CSV と profile の絞り込み条件を確認すること")
    ancient_events, sections = build_sections(selected, eras, profile)
    # 列幅の自動配分は、ソフト同期の区切りでも区間ごとの最長列が小さくなるように探す
    width_profile = {**profile, "sync_years": profile["sync_years"] or profile["soft_sync_years"]}
    _, width_sections = build_sections(selected, eras, width_profile)
    profile["column_layout"] = build_columns(profile, width_sections, eras)
    print("列幅: " + " / ".join(f"{column.heading or '（空欄）'} {column.width_mm:.0f}mm"
                               for column in profile["column_layout"]))

    version = f"{Path(profile['events_csv']).name} {event_rows} 行"
    version += f" + {Path(profile['local_csv']).name} {local_rows} 行" if profile["local_csv"] else ""
    data_info = {"built_on": today.isoformat(), "version": version, "profile_name": profile["name"]}
    assets = {"css": CSS_PATH.read_text(encoding="utf-8"), "js": FIT_JS_PATH.read_text(encoding="utf-8")}

    OUTPUT_DIR.mkdir(exist_ok=True)
    has_chrome = CHROME_PATH.exists()
    if not has_chrome:
        print(f"警告: Chrome が見つからない（{CHROME_PATH}）。HTML のみ出力する（ブラウザで開くと自動フィットが走る）")
    fit_result: dict = {}
    outputs: dict[str, Path] = {}
    for variant in VARIANTS:
        stem = f"timeline_{profile['name']}_{variant}"
        html_path = OUTPUT_DIR / f"{stem}.html"
        html_path.write_text(
            render_document(ancient_events, sections, eras, profile, assets, data_info, variant), encoding="utf-8"
        )
        print(f"HTML: {html_path.relative_to(PROJECT_ROOT)}")
        outputs[f"{variant}_html"] = html_path
        if not has_chrome:
            continue
        if variant == VARIANTS[0]:
            fit_result = read_fit_result(html_path)
        pdf_path = OUTPUT_DIR / f"{stem}.pdf"
        if print_to_pdf(html_path, pdf_path):
            print(f"PDF : {pdf_path.relative_to(PROJECT_ROOT)}（{count_pdf_pages(pdf_path)} ページ）")
            outputs[f"{variant}_pdf"] = pdf_path

    print(f"読込 {len(events)} 件 / profile で除外 {filtered_count} 件 / "
          f"紙面へ {len(selected)} 件（うち古代箱 {len(ancient_events)} 件）")
    if has_chrome:
        report_fit(fit_result, {event.event_id: event for event in selected})
    if not site_arg:
        return
    hidden_ids = set(fit_result.get("hidden-ids", "").split())
    shown_ids = {event.event_id for event in selected if event.track != LOCAL_TRACK} - hidden_ids
    site_dir = (Path.cwd() / site_arg).resolve()
    written = build_site(site_dir, profile, outputs, shown_ids, PROJECT_ROOT / profile["events_csv"], today.isoformat())
    print(f"公開サイト: {site_dir}（{len(written)} ファイル）")
    for path in written:
        print(f"  {path.relative_to(site_dir)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="精神医学史年表を HTML / PDF に描画する")
    parser.add_argument("profile", help="profiles/<name>.toml")
    parser.add_argument("--site", metavar="DIR", help="公開サイト一式（index.html・PDF・CSV ほか）をこのフォルダに出す")
    arguments = parser.parse_args()
    main(arguments.profile, arguments.site)
