#!/usr/bin/env python3
"""Fusionne names_batch.py dans local_names.py sans écraser les clés existantes."""
from __future__ import annotations

import re
from pathlib import Path

DIR = Path(__file__).parent
LOCAL_FILE = DIR / "local_names.py"
BATCH_FILE = DIR / "names_batch.py"

HEADER = '"""Dictionnaire local des noms mauritaniens et sénégalais (français et arabe)."""\n\n'
FOOTER = """
# Seuils fuzzy (RapidFuzz)
FUZZY_EXACT = 98
FUZZY_HIGH = 88
FUZZY_MEDIUM = 78
"""


def _load_dict_from_module(path: Path, var: str) -> dict:
    ns: dict = {}
    exec(path.read_text(encoding="utf-8"), ns)
    return dict(ns[var])


def _format_entry(key: str, entry: dict) -> str:
    norm = entry["normalized"].replace("\\", "\\\\").replace('"', '\\"')
    ar = entry["arabic"]
    return f'    "{key}": {{"normalized": "{norm}", "arabic": "{ar}"}},\n'


def main() -> None:
    if not BATCH_FILE.exists():
        raise SystemExit(f"Fichier manquant: {BATCH_FILE}")

    existing = _load_dict_from_module(LOCAL_FILE, "LOCAL_NAMES")
    batch = _load_dict_from_module(BATCH_FILE, "LOCAL_NAMES")

    added = 0
    skipped = 0
    merged = dict(existing)

    for key, entry in batch.items():
        lk = key.lower().strip()
        if lk in merged:
            skipped += 1
            continue
        merged[lk] = entry
        added += 1

    # Conserver l'ordre : entrées existantes puis nouvelles (triées)
    existing_keys = {k.lower() for k in existing}
    lines = [HEADER, "LOCAL_NAMES = {\n"]
    for key in existing:
        lines.append(_format_entry(key, existing[key]))
    for key in sorted(k for k in merged if k.lower() not in existing_keys):
        lines.append(_format_entry(key, merged[key]))
    lines.append("}\n")
    lines.append(FOOTER)

    LOCAL_FILE.write_text("".join(lines), encoding="utf-8")
    print(f"Ajoutés: {added}, ignorés (déjà présents): {skipped}, total: {len(merged)}")


if __name__ == "__main__":
    main()
