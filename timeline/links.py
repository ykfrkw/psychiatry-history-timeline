"""
Purpose: 項目クリックで出す外部リンク（Wikipedia／Amazon／PubMed）の検索語を data/links.csv から読み、links.js に渡す JS を作る
Inputs:  profile（link_menu, links_csv, amazon_tag）、表示する Event の一覧、timeline/links.js
Outputs: HTML に埋め込む JS 文字列（link_menu が false なら空文字）
Depends: csv, json, pathlib（標準ライブラリ）、timeline.data.Event
"""
import csv
import json
from pathlib import Path

from timeline.data import Event

LINKS_JS_PATH = Path(__file__).resolve().parent / "links.js"
DEFAULT_LINKS_CSV = "data/links.csv"
# 検索語から外す記号（書名の括弧などは Wikipedia 検索の邪魔になる）
SEARCH_STRIP_CHARS = "『』「」“”\"/"


def default_search_term(title: str) -> str:
    return "".join(char for char in title if char not in SEARCH_STRIP_CHARS).strip()


def load_link_rows(links_path: Path) -> dict[str, dict]:
    if not links_path.exists():
        return {}
    with links_path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["id"]: row for row in csv.DictReader(handle)}


def build_link_entries(events: list[Event], link_rows: dict[str, dict]) -> dict[str, dict]:
    """links.csv に行がない項目も、見出しで Wikipedia を検索できるようにする。"""
    entries = {}
    for event in events:
        row = link_rows.get(event.event_id, {})
        entry = {"n": default_search_term(event.title),
                 "w": row.get("wikipedia") or default_search_term(event.title)}
        if row.get("amazon"):
            entry["a"] = row["amazon"]
        if row.get("pubmed"):
            entry["p"] = row["pubmed"]
        entries[event.event_id] = entry
    return entries


def render_links_script(events: list[Event], profile: dict, project_root: Path) -> str:
    if not profile.get("link_menu", False):
        return ""
    link_rows = load_link_rows(project_root / profile.get("links_csv", DEFAULT_LINKS_CSV))
    entries = build_link_entries(events, link_rows)
    prelude = (f"const LINKS = {json.dumps(entries, ensure_ascii=False)};\n"
               f"const AMAZON_TAG = {json.dumps(profile.get('amazon_tag', ''))};\n")
    return prelude + LINKS_JS_PATH.read_text(encoding="utf-8")
