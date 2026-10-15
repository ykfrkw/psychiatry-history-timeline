"""
Purpose: 年表の profile と CSV（events / eras / local）を読み込み、検証して Event / Era に変換する
Inputs:  profiles/*.toml（Python 3.11 未満は *.json）、data/*.csv
Outputs: profile dict、list[Event]、list[Era]。検証で見つかった問題は標準出力に「警告」として出す
Depends: Python 標準ライブラリ（csv, dataclasses, pathlib）、timeline.profile_file
"""
import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from timeline.profile_file import read_profile_file

EVENT_COLUMNS = [
    "id", "year_start", "year_end", "year_label", "track", "title", "detail", "people",
    "region", "tags", "importance", "source", "source_url", "status", "emphasis",
]
CORE_TRACKS = ["world", "japan", "society", "diagnosis", "mind", "somatic"]
LOCAL_TRACK = "local"
VALID_TRACKS = set(CORE_TRACKS) | {LOCAL_TRACK}
# 旧スキーマの track は新しい列へ寄せる（データ側の移行が終わるまでの保険）
LEGACY_TRACKS = {"concept": "diagnosis", "treatment": "somatic"}
VALID_EMPHASIS = ("v", "h", "hl", "")  # hl＝横組みのハイライト見出し（縦帯と同じ配色）
TAG_SEPARATOR = ";"
SYNC_MODES = ("lowest", "anchor")
VALID_IMPORTANCE = (1, 2, 3)
FALLBACK_IMPORTANCE = 3
MIN_COLUMN_COUNT = 2
# 国名を全称で書いた行も紙面では 1〜2 字の略号にそろえる
REGION_ABBREVIATIONS = {
    "日本": "日", "ドイツ": "独", "フランス": "仏", "イギリス": "英", "アメリカ": "米", "オーストリア": "墺",
    "スイス": "瑞", "イタリア": "伊", "ロシア": "露", "ロ": "露", "ギリシャ": "希", "ギ": "希", "中国": "中",
    "オランダ": "蘭", "スペイン": "西", "ポルトガル": "葡", "ハンガリー": "洪", "オーストラリア": "豪",
    "ベルギー": "白", "カナダ": "加", "フィンランド": "芬", "チェコ": "捷", "インド": "印", "南アフリカ": "南ア",
    "スウェーデン": "典",
}
REGION_SEPARATOR = "・"  # 「スイス・スウェーデン」のような併記も 1 か国ずつ略号にする
CSV_ENCODING = "utf-8-sig"  # Excel で保存した BOM 付き CSV も読めるように

DEFAULT_COLUMNS = [
    {"track": "world", "heading": "隔離と解放", "sub": "世界の制度・思潮"},
    {"track": "japan", "heading": "監置から病院へ", "sub": "日本の制度・事件"},
    {"track": "society", "heading": "時代とこころ", "sub": "社会・文化"},
    {"track": "diagnosis", "heading": "病を名づける", "sub": "疾患概念・診断"},
    {"track": "mind", "heading": "こころを読む", "sub": "精神病理・精神療法"},
    {"track": "somatic", "heading": "からだに効かせる", "sub": "身体療法・薬物"},
]
DEFAULT_PROFILE = {
    "title": "精神医学の歴史",
    "subtitle": "",
    "corner_title": "",
    "essay": "",
    "events_csv": "data/events.csv",
    "eras_csv": "data/eras.csv",
    "local_csv": "",
    "local_heading": "医局",
    "local_sub": "医局の歩み",
    "local_after": "somatic",
    "local_blank": False,  # true なら local_csv が無くても空欄の医局列（手書き用の罫線）を出す
    "footer_note": "",  # 右ページ下端のフッタ（著作権・ライセンス・最新版の URL など）
    "blog_url": "",  # 公開サイト（--site）の「ブログ記事へ戻る」リンク
    "column_widths": "auto",
    "run_in": True,
    "show_legend": True,
    "show_era_index": True,
    "show_column_eras": True,
    "show_era_rules": False,
    "soft_sync_years": [],
    "soft_sync_tolerance_mm": 10,
    # lowest＝最も下の列に許容幅まで寄せる / anchor＝項目が最も多い列を動かさず、他の列をその高さに寄せる
    "sync_mode": "lowest",
    "sync_anchor_max_up_mm": 5,  # anchor のとき、基準列より上に残してよいずれ
    "sync_stops_bands": False,  # true なら縦帯の回り込みを同期線で止める（帯が下の年代に食い込まない）
    "font_step_pt": 0.1,
    "drop_levels": [3, 2],  # 溢れたら非表示にしてよい重要度（[] なら落とさず字を縮めるだけ）
    "show_band_labels": True,
    "show_bands": True,
    "columns": DEFAULT_COLUMNS,
    "color_tags": {},
    "include_tags": [],
    "exclude_tags": [],
    "keep_tags": ["exam"],
    "bold_tags": ["exam"],  # 重要度1に加えて太字にするタグ
    "max_importance": 3,
    "ancient_cutoff": 1800,
    "sync_years": [1900, 1950, 1995],
}
OBSOLETE_KEYS = ("segments", "tracks", "highlight_tags", "local_track_label", "local_column", "local_label")


@dataclass
class Event:
    event_id: str
    year_start: int
    year_end: int | None
    year_label: str
    track: str
    title: str
    detail: str
    people: str
    region: str
    tags: list[str]
    importance: int
    source: str
    emphasis: str

    @property
    def display_year(self) -> str:
        if self.year_label:
            return self.year_label
        if self.year_start < 0:
            return f"前{-self.year_start}"
        if self.year_end and self.year_end != self.year_start:
            return f"{self.year_start}–{self.year_end % 100:02d}"
        return str(self.year_start)

    def has_any_tag(self, tag_names) -> bool:
        return any(tag in self.tags for tag in tag_names)


@dataclass
class Era:
    start: int
    end: int
    label: str
    color: str


def warn(message: str) -> None:
    print(f"警告: {message}")


def load_profile(profile_path: Path) -> dict:
    loaded = read_profile_file(profile_path)
    for key in OBSOLETE_KEYS:
        if key in loaded:
            warn(f"profile の {key} は縦組み版では使わない（無視する）")
    profile = {**DEFAULT_PROFILE, **loaded}
    profile["name"] = profile_path.stem
    columns = profile["columns"]
    column_tracks = [column.get("track") for column in columns]
    # 列は減らしてよい（社会・文化を世界／日本に吸収した版など）。重複と未知の track だけ止める
    is_unknown = any(track not in CORE_TRACKS for track in column_tracks)
    if is_unknown or len(set(column_tracks)) != len(column_tracks) or len(columns) < MIN_COLUMN_COUNT:
        raise SystemExit(f"columns は {CORE_TRACKS} から重複なく {MIN_COLUMN_COUNT} 列以上を指定すること")
    if profile["local_after"] not in CORE_TRACKS:
        raise SystemExit(f"local_after は {CORE_TRACKS} のいずれか")
    if profile["sync_mode"] not in SYNC_MODES:
        raise SystemExit(f"sync_mode は {SYNC_MODES} のいずれか")
    return profile


def parse_int(text: str) -> int | None:
    try:
        return int(text.strip())
    except (ValueError, AttributeError):
        return None


def row_to_event(row: dict, where: str, forced_track: str | None, legacy_counter: Counter) -> Event | None:
    year_start = parse_int(row.get("year_start", ""))
    if year_start is None:
        warn(f"{where}: year_start が整数でない（{row.get('year_start')!r}）→ 読み飛ばし")
        return None
    track = forced_track or row.get("track", "").strip()
    if track in LEGACY_TRACKS:
        legacy_counter[track] += 1
        track = LEGACY_TRACKS[track]
    if track not in VALID_TRACKS:
        warn(f"{where}: track が不正（{track!r}）→ 読み飛ばし")
        return None
    importance = parse_int(row.get("importance", ""))
    if importance not in VALID_IMPORTANCE:
        warn(f"{where}: importance が 1/2/3 でない（{row.get('importance')!r}）→ 3 として扱う")
        importance = FALLBACK_IMPORTANCE
    emphasis = (row.get("emphasis") or "").strip().lower()
    if emphasis not in VALID_EMPHASIS:
        warn(f"{where}: emphasis が v/h/hl/空 でない（{emphasis!r}）→ 空として扱う")
        emphasis = ""
    if not row.get("source", "").strip():
        warn(f"{where}: source が空")
    raw_region = (row.get("region") or "").strip()
    raw_tags = row.get("tags", "") or ""
    return Event(
        event_id=row.get("id", "").strip(),
        year_start=year_start,
        year_end=parse_int(row.get("year_end", "")),
        year_label=row.get("year_label", "").strip(),
        track=track,
        title=row.get("title", "").strip(),
        detail=row.get("detail", "").strip(),
        people=row.get("people", "").strip(),
        region=REGION_SEPARATOR.join(REGION_ABBREVIATIONS.get(part, part) for part in raw_region.split(REGION_SEPARATOR)),
        tags=[tag.strip() for tag in raw_tags.split(TAG_SEPARATOR) if tag.strip()],
        importance=importance,
        source=row.get("source", "").strip(),
        emphasis=emphasis,
    )


def load_events(csv_path: Path, forced_track: str | None = None) -> tuple[list[Event], int]:
    """Return (events, data_row_count). forced_track は医局 CSV を医局の列（local）に寄せるため。"""
    if not csv_path.exists():
        warn(f"{csv_path} が見つからない")
        return [], 0
    events: list[Event] = []
    row_count = 0
    legacy_counter: Counter = Counter()
    with csv_path.open(encoding=CSV_ENCODING, newline="") as handle:
        reader = csv.reader(handle)
        header = [name.strip() for name in next(reader, [])]
        missing = [name for name in EVENT_COLUMNS if name not in header and name != "emphasis"]
        if missing:
            warn(f"{csv_path.name}: 列が足りない {missing}")
        for line_number, cells in enumerate(reader, start=2):
            if not any(cell.strip() for cell in cells):
                continue
            row_count += 1
            where = f"{csv_path.name}:{line_number}"
            if len(cells) != len(header):
                warn(f"{where}: 列数 {len(cells)}（ヘッダは {len(header)}）")
            event = row_to_event(dict(zip(header, cells)), where, forced_track, legacy_counter)
            if event:
                events.append(event)
    for legacy, count in legacy_counter.items():
        warn(f"{csv_path.name}: 旧 track {legacy!r} が {count} 行 → {LEGACY_TRACKS[legacy]!r} に寄せた")
    return events, row_count


def load_eras(csv_path: Path) -> list[Era]:
    if not csv_path.exists():
        raise SystemExit(f"{csv_path} が見つからない（縦組み版は時代で行を切るので必須）")
    eras: list[Era] = []
    with csv_path.open(encoding=CSV_ENCODING, newline="") as handle:
        for line_number, row in enumerate(csv.DictReader(handle), start=2):
            start, end = parse_int(row.get("start", "")), parse_int(row.get("end", ""))
            if start is None or end is None or end <= start:
                warn(f"{csv_path.name}:{line_number}: start/end が不正 → 読み飛ばし")
                continue
            eras.append(Era(start, end, row.get("label", "").strip(), row.get("color", "").strip()))
    eras.sort(key=lambda era: era.start)
    for previous, following in zip(eras, eras[1:]):
        if previous.end != following.start:
            warn(f"時代の境目が連続していない: {previous.label} の end {previous.end} / "
                 f"{following.label} の start {following.start}")
    if not eras:
        raise SystemExit(f"{csv_path.name} に有効な時代が無い")
    return eras


def is_protected(event: Event, profile: dict) -> bool:
    """自動調整で落とさない項目。"""
    return event.importance == 1 or bool(event.emphasis) or event.has_any_tag(profile["keep_tags"])


def select_events(events: list[Event], profile: dict) -> tuple[list[Event], int]:
    """profile の tag / importance 条件で絞る。Return (selected, filtered_out_count)。"""
    selected = []
    for event in events:
        is_kept_by_tag = event.has_any_tag(profile["keep_tags"])
        is_included = not profile["include_tags"] or event.has_any_tag(profile["include_tags"])
        is_excluded = event.has_any_tag(profile["exclude_tags"])
        is_within_importance = event.importance <= profile["max_importance"]
        # 除外タグ（未確認の項目など）は keep_tags より優先する。誤りを載せない方が大事なので
        if is_excluded:
            continue
        if is_kept_by_tag or (is_included and is_within_importance):
            selected.append(event)
    return selected, len(events) - len(selected)


@dataclass
class Section:
    """全列の高さをそろえる区間（grid の 1 行）。end が None なら現在まで。"""
    start: int
    end: int | None
    eras: list[Era]
    events: list[Event]


def era_of(year: int, eras: list[Era]) -> Era | None:
    return next((era for era in eras if era.start <= year < era.end), None)


def build_sections(events: list[Event], eras: list[Era], profile: dict) -> tuple[list[Event], list[Section]]:
    """Return (ancient_events, sections)。区間は [ancient_cutoff, sync_years..., 現在]。"""
    cutoff = profile["ancient_cutoff"]
    sync_years = sorted(year for year in profile["sync_years"] if year > cutoff)
    bounds = [cutoff, *sync_years, None]
    ordered = sorted(events, key=lambda event: (event.year_start, event.event_id))
    ancient = [event for event in ordered if event.year_start < cutoff]
    sections = []
    for start, end in zip(bounds, bounds[1:]):
        overlapping = [era for era in eras if era.end > start and (end is None or era.start < end)]
        members = [event for event in ordered if event.year_start >= start and (end is None or event.year_start < end)]
        sections.append(Section(start, end, overlapping, members))
    for event in ordered:
        if event.year_start >= cutoff and era_of(event.year_start, eras) is None:
            warn(f"{event.event_id} {event.year_start} がどの時代にも入らない（列内の時代見出しなし）")
    return ancient, sections
