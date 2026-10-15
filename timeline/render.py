"""
Purpose: 420×297mm の 1 枚キャンバス（左余白＝タイトル・論評・古代箱・凡例／見開き本体／フッタ）の HTML を作り、A3 版と A4×2 版にする
Inputs:  古代箱の Event、list[Section]（区間ごとの Event）、list[Era]、profile dict、template.css と fit.js の中身、データ版の情報
Outputs: HTML 文字列（CSS / JS は埋め込み。out/ の HTML 単体で開ける）
Depends: timeline.spread, timeline.data, html（標準ライブラリ）
"""
from timeline.data import Era, Event, Section
from pathlib import Path

from timeline.links import render_links_script
from timeline.spread import esc, region_html, render_spread

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CANVAS_W_MM = 420
CANVAS_H_MM = 297
A4_WIDTH_MM = CANVAS_W_MM // 2
# 縦書きタイトルは 1 列に収める。長い題（医局版など）は字を小さくする
SIDE_HEAD_H_MM = 118
TITLE_MAX_PT = 25
TITLE_ADVANCE_EM = 1.14  # 字間 0.12em ＋ 余裕
MM_PER_PT = 25.4 / 72
REGION_NAMES = {
    "日": "日本", "独": "ドイツ", "仏": "フランス", "英": "イギリス", "米": "アメリカ", "墺": "オーストリア",
    "瑞": "スイス", "典": "スウェーデン", "伊": "イタリア", "露": "ロシア", "希": "ギリシャ", "羅": "ローマ", "中": "中国",
    "蘭": "オランダ", "西": "スペイン", "葡": "ポルトガル", "洪": "ハンガリー", "豪": "オーストラリア",
    "白": "ベルギー", "加": "カナダ", "芬": "フィンランド", "捷": "チェコ", "印": "インド", "南ア": "南アフリカ",
    "国連": "国際連合", "北欧": "北欧", "欧": "ヨーロッパ", "国": "国際機関（WHO 等）", "ペ": "ペルシア",
}
# フッタの高さは行数で変える（1 行の版で 2 行ぶん空けると、その分だけ本文の字が小さくなる）
FOOT_HEIGHT_MM = {1: 4.0, 2: 6.4}
TAG_MEANINGS = {"ethics": "倫理・人権", "sleep": "睡眠", "law": "法制度", "drug": "薬物", "exam": "国試頻出"}


def render_ancient(ancient_events: list[Event], profile: dict) -> str:
    if not ancient_events:
        return ""
    items = []
    for event in ancient_events:
        css = ["ancient-item"]
        if event.importance == 1 or event.has_any_tag(profile["bold_tags"]):
            css.append("strong")
        if event.emphasis:
            css.append("emph")
        items.append(
            f'<div class="{" ".join(css)}" data-id="{esc(event.event_id)}" style="--accent:var(--col-{event.track})" '
            f'title="{esc(event.detail)}">'
            f'<span class="mk"></span><span class="yr">{esc(event.display_year)}</span>'
            f'{esc(event.title)}{region_html(event)}</div>'
        )
    return (f'<section class="ancient"><div class="side-box-head">古代〜{profile["ancient_cutoff"] - 1}</div>'
            f'{"".join(items)}</section>')


def used_regions(events: list[Event]) -> str:
    codes = sorted({event.region for event in events if event.region})
    return "".join(f"<span>{esc(code)}＝{esc(REGION_NAMES.get(code, code))}</span>" for code in codes)


def render_legend(shown_events: list[Event], profile: dict) -> str:
    swatches = "".join(
        f'<div><span class="sw" style="background:var(--col-{column.track})"></span>'
        f'{esc(column.sub or column.heading)}</div>'
        for column in profile["column_layout"]
    )
    colored = "".join(
        f'<div><span style="color:{color}">■</span> 色付きの本文＝{esc(TAG_MEANINGS.get(tag, tag))}</div>'
        for tag, color in profile["color_tags"].items()
    )
    keep = "・".join(TAG_MEANINGS.get(tag, tag) for tag in profile["keep_tags"])
    return (f'<section class="legend"><div class="side-box-head">凡例</div>{swatches}'
            f'<div class="legend-gap"><b>太字</b>＝重要度1・{esc(keep)}</div>{colored}'
            f'<div class="legend-gap regions">{used_regions(shown_events)}</div></section>')


def render_side_left(ancient_events: list[Event], shown_events: list[Event], profile: dict) -> str:
    essay = f'<p class="essay">{esc(profile["essay"])}</p>' if profile["essay"] else ""
    subtitle = f'<p class="subtitle">{esc(profile["subtitle"])}</p>' if profile["subtitle"] else ""
    title_pt = min(TITLE_MAX_PT, SIDE_HEAD_H_MM / (len(profile["title"]) * TITLE_ADVANCE_EM) / MM_PER_PT)
    return (f'<aside class="side-left"><div class="side-head" style="height:{SIDE_HEAD_H_MM}mm">'
            f'<h1 class="title" style="font-size:{title_pt:.1f}pt">{esc(profile["title"])}</h1>'
            f'{subtitle}{essay}</div>{render_ancient(ancient_events, profile)}'
            f'{render_legend(shown_events, profile) if profile["show_legend"] else ""}</aside>')


def render_footer(data_info: dict, profile: dict) -> str:
    """凡例は左余白へ移したので、フッタは版の情報だけ（左ページの下端、ノドを跨がない）。"""
    return (f'<footer class="foot foot-left">作成 {esc(data_info["built_on"])}　データ版 {esc(data_info["version"])}　'
            f'profile: {esc(data_info["profile_name"])}　'
            f'出典は CSV の source 列（HTML 版はマウスで補足・出典を表示）</footer>')


def affiliate_note(profile: dict) -> str:
    # Amazon アソシエイトの表示義務。リンクメニューを出す版だけに付ける
    if not (profile.get("link_menu") and profile.get("amazon_tag")):
        return ""
    return ("項目をクリックすると Amazon・Wikipedia・PubMed へのリンクを表示。Amazon アソシエイト・プログラムに参加しています"
            "（Amazon のアソシエイトとして適格販売により収入を得ています）")


def footer_note_parts(profile: dict) -> list[str]:
    # 左ページのフッタに入れるとノドで切れるので、アソシエイト表記も右ページ側に置く
    return [part for part in (affiliate_note(profile), profile["footer_note"]) if part]


def render_footer_note(profile: dict) -> str:
    """右ページの下端（ノドを跨がない）に著作権・ライセンス表記。空なら出さない。"""
    parts = footer_note_parts(profile)
    return f'<footer class="foot foot-right">{"<br>".join(esc(part) for part in parts)}</footer>' if parts else ""


def render_canvas(body: str, foot_height_mm: float, offset_mm: int = 0) -> str:
    return f'<div class="canvas" style="left:{offset_mm}mm;--foot-h:{foot_height_mm:g}mm">{body}</div>'


def render_document(ancient_events: list[Event], sections: list[Section], eras: list[Era],
                    profile: dict, assets: dict, data_info: dict, variant: str) -> str:
    shown_events = ancient_events + [event for section in sections for event in section.events]
    body = (render_side_left(ancient_events, shown_events, profile) + render_spread(sections, eras, profile)
            + render_footer(data_info, profile) + render_footer_note(profile)
            + f'<div class="gutter-mark top"></div><div class="gutter-mark bottom"></div>')
    foot_lines = min(max(len(footer_note_parts(profile)), 1), max(FOOT_HEIGHT_MM))
    foot_height_mm = FOOT_HEIGHT_MM[foot_lines]
    if variant == "A3":
        page_size = f"{CANVAS_W_MM}mm {CANVAS_H_MM}mm"
        pages = f'<div class="page page-a3">{render_canvas(body, foot_height_mm)}</div>'
    else:
        page_size = f"{A4_WIDTH_MM}mm {CANVAS_H_MM}mm"
        pages = (f'<div class="page page-a4">{render_canvas(body, foot_height_mm)}</div>'
                 f'<div class="page page-a4">{render_canvas(body, foot_height_mm, -A4_WIDTH_MM)}</div>')
    return (
        "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">"
        f"<title>{esc(profile['title'])}（{variant}）</title>"
        f"<style>@page {{ size: {page_size}; margin: 0; }}\n{assets['css']}</style></head>"
        f"<body>{pages}<script>{assets['js']}</script>"
        f"<script>{render_links_script(shown_events, profile, PROJECT_ROOT)}</script></body></html>"
    )
