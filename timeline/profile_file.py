"""
Purpose: profile（TOML / JSON）を読む。extends で別 profile を土台にできる（共通の土台 base.toml から公開版・医局版を作る等）
Inputs:  profiles/*.toml または *.json のパス
Outputs: dict（extends を解決済み。既定値の補完は data.load_profile が行う）
Depends: Python 標準ライブラリ（json, tomllib, pathlib）
"""
import json
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 以前
    tomllib = None


def read_profile_file(profile_path: Path) -> dict:
    """extends = "base.toml" のように別 profile を土台にでき、書いたキーだけ上書きする（正本を 1 つに保つため）。"""
    if profile_path.suffix == ".json":
        loaded = json.loads(profile_path.read_text(encoding="utf-8"))
    elif tomllib is None:
        raise SystemExit("Python 3.11 未満では TOML を読めない。profile を .json で用意すること")
    else:
        loaded = tomllib.loads(profile_path.read_text(encoding="utf-8"))
    base_name = loaded.pop("extends", "")
    return {**read_profile_file(profile_path.parent / base_name), **loaded} if base_name else loaded
