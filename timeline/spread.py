"""
Purpose: 見開きの本体（列ヘッダ・区間帯・区間×6列のセル・右余白の時代索引）を CSS grid の HTML にする。
         全列の高さをそろえるのは sync_years の区間の境だけ。区間の中では各列が独立に流れ、
         時代（eras.csv）は列ごとに、その時代の最初の項目の手前へ小見出しとして入る
Inputs:  list[Section]（timeline.data.build_sections）、list[Era]、profile dict
Outputs: <div class="spread"> の HTML 文字列。列内の組版（流し込み・回り込み）はブラウザに任せる
Depends: timeline.data, html（標準ライブラリ）
"""
import html
import re
from itertools import groupby

from timeline.columns import Column, grid_template
from timeline.data import Era, Event, Section, era_of, is_protected

# 列見出しは列幅に合わせて字を縮める（狭い列でも 1 行に収める）
HEADING_MAX_PT = 12.5
HEADING_MIN_PT = 8.0
HEADING_PADDING_MM = 3.6
HEADING_ADVANCE_EM = 1.12  # 見出しの字間（letter-spacing）ぶん、1字の送りは 1em より広い
MM_PER_PT = 25.4 / 72
ERA_PALETTE_SIZE = 7
TCY_MAX_CHARS = 2
SECTION_LABEL_SEPARATOR = " ／ "
ASCII_RUN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-.]*")
HEADLINE_PALETTE_SIZE = 4
# hl は h と同じ組み（見出し＋detail）で、色だけ縦帯と同じ列色にする
HEADLINE_EMPHASIS = ("h", "hl")
# 年ガターは 4 桁ぶん。1970s・1950頃 など長い年は縮めて収める
YEAR_GUTTER_CHARS = 4
YEAR_ONE_LINE_MAX_CHARS = 5  # 1970s・1950頃 は縮めれば 1 行。1980年代 は 2 行
YEAR_RANGE_PATTERN = re.compile(r"^(\d{4})–(\d{4})$")
# 各国の項目でも、その列で自明な国名は省く
HIDDEN_REGION_BY_TRACK = {"japan": "日", "local": "日"}


def esc(text) -> str:
    return html.escape(str(text), quote=True)


def range_text(start: int, end: int | None, current_year: int) -> str:
    """半開区間 [start, end) を「1900–1949」に。今年を含むなら「–現在」。"""
    if end is None or end - 1 >= current_year:
        return f"{start}–現在"
    return f"{start}–{end - 1}"


def era_color(era: Era, index: int) -> str:
    return era.color or f"var(--era-{index % ERA_PALETTE_SIZE})"


def region_html(event: Event) -> str:
    is_hidden = not event.region or HIDDEN_REGION_BY_TRACK.get(event.track) == event.region
    return "" if is_hidden else f'<span class="rg">［{esc(event.region)}］</span>'


def text_color(event: Event, profile: dict) -> str:
    for tag, color in profile["color_tags"].items():
        if tag in event.tags:
            return color
    return ""


def item_attributes(event: Event, profile: dict, css_classes: list[str]) -> str:
    if event.importance == 1 or event.has_any_tag(profile["bold_tags"]):
        css_classes.append("strong")
    drop_level = "" if is_protected(event, profile) else str(event.importance)
    tooltip = " / ".join(part for part in (event.detail, event.people, event.source) if part)
    color = text_color(event, profile)
    style = f' style="color:{color}"' if color else ""
    return (f'class="{" ".join(css_classes)}" data-id="{esc(event.event_id)}" '
            f'data-drop="{drop_level}" title="{esc(tooltip)}"{style}')


def vertical_html(text: str) -> str:
    """縦書きで、2 字以下の英数（T4 など）は縦中横、3 字以上（DSM-III など）は横倒しのまま。"""
    return ASCII_RUN_PATTERN.sub(
        lambda match: f'<span class="tcy">{match.group(0)}</span>' if len(match.group(0)) <= TCY_MAX_CHARS
        else match.group(0),
        esc(text),
    )


VBAND_LINE_BREAK = "/"  # title に入れると縦帯を 2 列以上に分けて組む（長い帯を短く立てる）


def render_vertical_band(title: str) -> str:
    """縦帯は title の / の位置でだけ改行する。列に収まらないときは fit.js が帯の字を小さくする。"""
    lines = "<br>".join(vertical_html(part) for part in title.split(VBAND_LINE_BREAK))
    return f'<div class="vband">{lines}</div>'


def render_item(event: Event, profile: dict, headline_counter: list[int]) -> str:
    base_classes = ["it"]
    if event.emphasis == "v":
        band = render_vertical_band(event.title)
        body = esc(event.detail) if event.detail else ""
        return band + f'<div {item_attributes(event, profile, base_classes + ["v-item"])}>{body}{region_html(event)}</div>'
    if event.emphasis in HEADLINE_EMPHASIS:
        hue = f"var(--kw-{headline_counter[0] % HEADLINE_PALETTE_SIZE})"
        headline_counter[0] += 1
        keyword_class = "kw kw-hl" if event.emphasis == "hl" else "kw"
        # detail が無いときは地域を見出しの行末に置き、地域だけの行を作らない
        inline_region = "" if event.detail else region_html(event)
        detail = f'<div class="kw-detail">{esc(event.detail)}{region_html(event)}</div>' if event.detail else ""
        return (f'<div {item_attributes(event, profile, base_classes + ["h-item"])}>'
                f'<div class="{keyword_class}" style="--kw:{hue}">{esc(event.title)}{inline_region}</div>{detail}</div>')
    return f'<div {item_attributes(event, profile, base_classes)}>{esc(event.title)}{region_html(event)}</div>'


def render_run_in(events: list[Event], profile: dict) -> str:
    """同じ年の通常項目を 1 段落に追い込む（『情報の歴史』の年ブロックと同じ組み方）。太字・色は項目ごと。"""
    spans = "".join(
        f'<span {item_attributes(event, profile, ["it"])}>{esc(event.title)}{region_html(event)}</span>'
        for event in events
    )
    return f'<div class="run">{spans}</div>'


def render_year_items(year_events: list[Event], profile: dict, headline_counter: list[int]) -> str:
    if not profile["run_in"]:
        return "".join(render_item(event, profile, headline_counter) for event in year_events)
    parts = []
    for is_plain, group in groupby(year_events, key=lambda event: not event.emphasis):
        group = list(group)
        if is_plain:
            parts.append(render_run_in(group, profile))
        else:
            parts.extend(render_item(event, profile, headline_counter) for event in group)
    return "".join(parts)


def gutter_year_html(year_text: str) -> str:
    """期間の年は 2 行にし、同じ世紀なら終わりを下 2 桁にする（1901–1925 → 1901 / –25）。"""
    match = YEAR_RANGE_PATTERN.match(year_text)
    if match and match.group(1)[:2] == match.group(2)[:2]:
        return f'{match.group(1)}<br><span class="yr-end">–{match.group(2)[2:]}</span>'
    start, separator, end = esc(year_text).partition("–")
    return f'{start}<br><span class="yr-end">–{end}</span>' if separator else start


def render_cell(events: list[Event], eras: list[Era], profile: dict, headline_counter: list[int]) -> str:
    blocks = []
    current_era = None
    pending_syncs = sorted(profile["soft_sync_years"])
    for year_text, year_events in groupby(events, key=lambda event: event.display_year):
        year_events = list(year_events)
        era = era_of(year_events[0].year_start, eras)
        # ソフト同期の目印。fit.js が列間のずれを許容幅まで詰める（完全にはそろえない）
        has_sync_mark = False
        while pending_syncs and year_events[0].year_start >= pending_syncs[0]:
            blocks.append(f'<div class="sync-rule" data-sync="{pending_syncs.pop(0)}"></div>')
            has_sync_mark = True
        if has_sync_mark:
            current_era = era
        if profile["show_column_eras"] and era is not None and era is not current_era:
            color = era_color(era, eras.index(era))
            blocks.append(f'<div class="era-sub" style="--era:{color}">{esc(era.label)}</div>')
            current_era = era
        elif profile["show_era_rules"] and era is not None and era is not current_era:
            # 時代の境を列の中の破線で示す（セルの先頭は区間の罫と重なるので引かない）
            if current_era is not None:
                blocks.append('<div class="era-rule"></div>')
            current_era = era
        year_html = gutter_year_html(year_text)
        year_class = "yr yr-long" if len(year_text) > YEAR_GUTTER_CHARS and "–" not in year_text else "yr"
        # 2 行になる年が次のブロックに重ならないように
        is_two_lines = "–" in year_text or len(year_text) > YEAR_ONE_LINE_MAX_CHARS
        block_class = "yb yb-range" if is_two_lines else "yb"
        # 大見出し・縦帯の項目は同年の追い込み項目と別ブロックにし、年を付け直す（1 つの出来事に見えないように）
        for chunk in split_year_chunks(year_events):
            items = render_year_items(chunk, profile, headline_counter)
            blocks.append(f'<div class="{block_class}"><span class="{year_class}">{year_html}</span>{items}</div>')
    return "".join(blocks)


def split_year_chunks(year_events: list[Event]) -> list[list[Event]]:
    chunks = []
    for is_plain, group in groupby(year_events, key=lambda event: not event.emphasis):
        group = list(group)
        chunks.extend([group] if is_plain else [[event] for event in group])
    return chunks


def render_blank_cell(section: Section, profile: dict) -> str:
    """手書き用の空欄セル。中身は置かず、等間隔の罫線（template.css の .cell-blank）だけにする。"""
    return ""


def heading_pt(heading: str, width_mm: float) -> float:
    fitting_pt = (width_mm - HEADING_PADDING_MM) / (max(len(heading), 1) * HEADING_ADVANCE_EM) / MM_PER_PT
    return max(HEADING_MIN_PT, min(HEADING_MAX_PT, fitting_pt))


def render_column_heads(columns: list[Column], profile: dict, index_column: int) -> list[str]:
    heads = []
    for column in columns:
        # 列名も空欄なら白地の枠だけ（印刷後に手書きで列名を書く）
        head_class = "col-head col-head-blank" if not (column.heading or column.sub) else "col-head"
        heads.append(
            f'<div class="{head_class}" style="grid-row:1;grid-column:{column.grid_index};--accent:var(--col-{column.track})">'
            f'<span class="col-heading" style="font-size:{heading_pt(column.heading, column.width_mm):.1f}pt">'
            f'{esc(column.heading)}</span><span class="col-sub">{esc(column.sub)}</span></div>'
        )
    corner = profile["corner_title"]
    if corner and profile["show_era_index"]:
        heads.append(f'<div class="corner" style="grid-row:1;grid-column:{index_column}">{esc(corner)}</div>')
    return heads


def render_section_band(section: Section, band_row: int, band_columns: str, current_year: int,
                        has_labels: bool = True) -> str:
    labels = SECTION_LABEL_SEPARATOR.join(esc(era.label) for era in section.eras) if has_labels else ""
    return (f'<div class="era-band" style="grid-row:{band_row};grid-column:{band_columns}">'
            f'<span class="era-label">{labels}</span>'
            f'<span class="era-range">{range_text(section.start, section.end, current_year)}</span></div>')


def render_section_index(section: Section, band_row: int, index_column: int, eras: list[Era],
                         current_year: int) -> str:
    entries = "".join(
        f'<div class="era-index-entry" style="--era:{era_color(era, eras.index(era))}">'
        f'<span class="era-index-label">{esc(era.label)}</span>'
        f'<span class="era-index-range">{range_text(era.start, era.end, current_year)}</span></div>'
        for era in section.eras
    )
    return f'<div class="era-index" style="grid-row:{band_row} / span 2;grid-column:{index_column}">{entries}</div>'


def render_spread(sections: list[Section], eras: list[Era], profile: dict) -> str:
    columns: list[Column] = profile["column_layout"]
    last_grid_index = max(column.grid_index for column in columns)
    band_columns = f"1 / {last_grid_index + 1}"  # 帯はノドを含む全列を横切る
    index_column = last_grid_index + 2  # 索引との間の空きを 1 つ挟む
    page_first = {min(c.grid_index for c in columns if c.page == page) for page in ("left", "right")}
    parts = render_column_heads(columns, profile, index_column)
    current_year = profile["current_year"]
    headline_counter = [0]
    for section_index, section in enumerate(sections):
        band_row, content_row = 2 + 2 * section_index, 3 + 2 * section_index
        if profile["show_bands"]:
            parts.append(render_section_band(section, band_row, band_columns, current_year,
                                              profile["show_band_labels"]))
        if profile["show_era_index"]:
            parts.append(render_section_index(section, band_row, index_column, eras, current_year))
        for column in columns:
            column_events = [event for event in section.events if event.track == column.track]
            first_class = " col-first" if column.grid_index in page_first else ""
            first_class += " cell-blank" if column.is_blank else ""
            flow = (render_blank_cell(section, profile) if column.is_blank
                    else render_cell(column_events, eras, profile, headline_counter))
            parts.append(
                f'<div class="cell{first_class}" data-era="{section_index}" '
                f'style="grid-row:{content_row};grid-column:{column.grid_index};--accent:var(--col-{column.track});'
                f'--tint:var(--tint-{column.track})">'
                f'<div class="flow">{flow}</div></div>'
            )
    is_anchor = profile["sync_mode"] == "anchor"
    tolerance = profile["sync_anchor_max_up_mm"] if is_anchor else profile["soft_sync_tolerance_mm"]
    drop_levels = " ".join(str(level) for level in profile["drop_levels"])
    spread_class = "spread sync-stops-bands" if profile["sync_stops_bands"] else "spread"
    return (f'<div class="{spread_class}" data-sync-tol="{tolerance}" data-sync-mode="{profile["sync_mode"]}" '
            f'data-font-step="{profile["font_step_pt"]}" data-drop-levels="{drop_levels}" '
            f'style="grid-template-columns:{grid_template(columns, profile["show_era_index"])}">{"".join(parts)}</div>')
