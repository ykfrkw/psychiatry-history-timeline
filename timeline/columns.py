"""
Purpose: 見開きの列構成（6 列＋医局列。local_blank なら手書き用の空欄列）と各列の幅（mm）を決める。既定（auto）は、列ごと・区間ごとの行数を
         字数から見積もり、「各区間で最も長い列の高さ」の合計が最小になる幅を 1mm 刻みで探す
Inputs:  profile dict（columns / local_* / column_widths / run_in）、list[Section]
Outputs: list[Column]（左ページ→右ページの順。grid の列番号つき）と grid-template-columns の文字列
Depends: timeline.data（Event, LOCAL_TRACK）。寸法は template.css の --spread-x 等と一致させること
"""
from dataclasses import dataclass
from itertools import groupby

from timeline.data import LOCAL_TRACK, Event, Section, era_of, warn

# 版面の横幅（template.css と一致）。左は x=34〜205mm、右は 215〜393mm、ノド 10mm
PAGE_WIDTH_MM = {"left": 171.0, "right": 178.0}
GUTTER_MM = 10.0
INDEX_GAP_MM = 2.0
INDEX_WIDTH_MM = 19.0
MIN_COLUMN_MM = 32.0
MAX_RATIO_OF_EVEN = 1.6
# 年ガターとセルの余白は列幅に関係なく要るので、比例配分の対象から外す
FIXED_OVERHEAD_MM = 8.0
LEFT_PAGE_CORE_COLUMNS = 3  # 左ページ＝制度と社会（世界・日本）、右ページ＝医学の列＋医局
# 行数の見積もりは本文 5.5pt を想定（fit.js の結果に近い大きさ）。比率は template.css と一致させる
ESTIMATE_FONT_MM = 5.5 * 25.4 / 72
KEYWORD_RATIO = 1.6
HIGHLIGHT_RATIO = 2.2
HEADLINE_RATIOS = {"h": KEYWORD_RATIO, "hl": HIGHLIGHT_RATIO}
VBAND_RATIO = 2.45
YEAR_BLOCK_GAP_LINES = 0.15
ERA_HEAD_LINES = 1.6
REGION_BRACKET_CHARS = 2
SEARCH_STEP_MM = 1.0
PARTIAL_LINE_ALLOWANCE = 0.5
# 最長列以外も少しは縮んだ方がよいので、全セルの高さを小さな重みで目的関数に足す
ALL_CELLS_WEIGHT = 0.02
MAX_SEARCH_STEPS = 400


@dataclass
class Column:
    track: str
    heading: str
    sub: str
    page: str
    width_mm: float = 0.0
    grid_index: int = 0
    is_blank: bool = False  # 手書き用の空欄列（項目を入れず、罫線と年の目安だけ）


def text_chars(event: Event) -> int:
    return len(event.title) + (len(event.region) + REGION_BRACKET_CHARS if event.region else 0)


def lines_for(chars: float, chars_per_line: float) -> float:
    """行数。切り上げると 1mm 刻みの探索が平坦になって動かないので、半行の余りを足した連続値で近似する。"""
    return max(1.0, chars / chars_per_line + PARTIAL_LINE_ALLOWANCE)


def year_block_lines(year_events: list[Event], chars_per_line: float, is_run_in: bool) -> float:
    lines = YEAR_BLOCK_GAP_LINES
    for is_plain, group in groupby(year_events, key=lambda event: not event.emphasis):
        group = list(group)
        if is_plain and is_run_in:
            lines += lines_for(sum(text_chars(event) + 1 for event in group), chars_per_line)
            continue
        for event in group:
            detail_chars = len(event.detail) + REGION_BRACKET_CHARS if event.emphasis else 0
            if event.emphasis in HEADLINE_RATIOS:
                ratio = HEADLINE_RATIOS[event.emphasis]
                lines += lines_for(len(event.title) * ratio, chars_per_line) * ratio
                lines += lines_for(detail_chars, chars_per_line) if event.detail else 0
            elif event.emphasis == "v":
                lines += lines_for(detail_chars, chars_per_line)
            else:
                lines += lines_for(text_chars(event), chars_per_line)
    return lines


def estimate_height(events: list[Event], width_mm: float, eras, is_run_in: bool) -> float:
    """1 区間・1 列の高さ（本文の行数単位）。縦帯は回り込むので、帯の長さとの大きい方を取る。"""
    if not events:
        return 0.0
    chars_per_line = max((width_mm - FIXED_OVERHEAD_MM) / ESTIMATE_FONT_MM, 1.0)
    year_groups = [list(group) for _, group in groupby(events, key=lambda event: event.display_year)]
    era_heads = len({id(era_of(group[0].year_start, eras)) for group in year_groups})
    text_lines = sum(year_block_lines(group, chars_per_line, is_run_in) for group in year_groups)
    band_lines = max((len(e.title) * VBAND_RATIO for e in events if e.emphasis == "v"), default=0.0)
    return max(text_lines + era_heads * ERA_HEAD_LINES, band_lines)


def total_height(columns: list[Column], widths: list[float], cells: dict, eras, is_run_in: bool) -> float:
    total = 0.0
    for section_index in {key[0] for key in cells}:
        heights = [estimate_height(cells[(section_index, column.track)], width, eras, is_run_in)
                   for column, width in zip(columns, widths)]
        total += max(heights) + ALL_CELLS_WEIGHT * sum(heights)
    return total


def page_widths(profile: dict) -> dict[str, float]:
    # 索引を出さない版では、索引と空きのぶんを右ページの本文に回す
    if profile["show_era_index"]:
        return dict(PAGE_WIDTH_MM)
    return {**PAGE_WIDTH_MM, "right": PAGE_WIDTH_MM["right"] + INDEX_GAP_MM + INDEX_WIDTH_MM}


def search_widths(columns: list[Column], sections: list[Section], eras, is_run_in: bool,
                  page_width_mm: dict[str, float]) -> list[float]:
    """均等幅から始め、同じページの 2 列の間で 1mm ずつ幅を移して、合計の高さが下がる限り続ける。"""
    cells = {(i, column.track): [e for e in section.events if e.track == column.track]
             for i, section in enumerate(sections) for column in columns}
    widths = []
    bounds = {}
    for page, page_width in page_width_mm.items():
        count = sum(1 for column in columns if column.page == page)
        bounds[page] = (MIN_COLUMN_MM, page_width / count * MAX_RATIO_OF_EVEN)
    widths = [page_width_mm[column.page] / sum(1 for c in columns if c.page == column.page) for column in columns]
    best = total_height(columns, widths, cells, eras, is_run_in)
    for _ in range(MAX_SEARCH_STEPS):
        best_move = None
        for gain in range(len(columns)):
            for give in range(len(columns)):
                low, high = bounds[columns[gain].page]
                is_same_page = gain != give and columns[gain].page == columns[give].page
                if not is_same_page or widths[gain] + SEARCH_STEP_MM > high or widths[give] - SEARCH_STEP_MM < low:
                    continue
                trial = widths.copy()
                trial[gain] += SEARCH_STEP_MM
                trial[give] -= SEARCH_STEP_MM
                height = total_height(columns, trial, cells, eras, is_run_in)
                if height < best - 1e-9:
                    best, best_move = height, trial
        if best_move is None:
            break
        widths = best_move
    return widths


def order_columns(profile: dict) -> list[Column]:
    columns = []
    for index, spec in enumerate(profile["columns"]):
        page = "left" if index < LEFT_PAGE_CORE_COLUMNS else "right"
        columns.append(Column(spec["track"], spec.get("heading", ""), spec.get("sub", ""), page))
        has_local_column = bool(profile["local_csv"]) or profile["local_blank"]
        if has_local_column and spec["track"] == profile["local_after"]:
            is_blank = not profile["local_csv"]
            columns.append(Column(LOCAL_TRACK, profile["local_heading"], profile["local_sub"], page, is_blank=is_blank))
    return columns


def assign_widths(columns: list[Column], sections: list[Section], eras, profile: dict) -> None:
    setting = profile["column_widths"]
    if isinstance(setting, list) and len(setting) != len(columns):
        warn(f"column_widths の要素数 {len(setting)} が列数 {len(columns)} と違う → auto で配分")
        setting = "auto"
    if not isinstance(setting, list):
        for column, width in zip(columns, search_widths(columns, sections, eras, profile["run_in"], page_widths(profile))):
            column.width_mm = width
        return
    for page, page_width in page_widths(profile).items():
        page_columns = [(i, column) for i, column in enumerate(columns) if column.page == page]
        ratio_sum = sum(float(setting[i]) for i, _ in page_columns) or 1.0
        for i, column in page_columns:
            column.width_mm = page_width * float(setting[i]) / ratio_sum


def build_columns(profile: dict, sections: list[Section], eras) -> list[Column]:
    columns = order_columns(profile)
    assign_widths(columns, sections, eras, profile)
    left_count = sum(1 for column in columns if column.page == "left")
    for index, column in enumerate(columns):
        # grid の列番号: 左ページ 1..L、ノド L+1、右ページ L+2..
        column.grid_index = index + 1 if column.page == "left" else index + 2
    if left_count == 0 or left_count == len(columns):
        raise SystemExit("左右のページに列が 1 本以上必要")
    return columns


def grid_template(columns: list[Column], has_index: bool = True) -> str:
    left = " ".join(f"{c.width_mm:.2f}mm" for c in columns if c.page == "left")
    right = " ".join(f"{c.width_mm:.2f}mm" for c in columns if c.page == "right")
    if not has_index:
        return f"{left} {GUTTER_MM:g}mm {right}"
    return f"{left} {GUTTER_MM:g}mm {right} {INDEX_GAP_MM:g}mm {INDEX_WIDTH_MM:g}mm"
