"""Traitement batch : CSV, Excel, texte."""

import io
import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.services.entity_extractor import detect_name_columns, extract_names_from_text

logger = logging.getLogger(__name__)

MAX_BATCH_ROWS = 2000


def parse_upload_content(
    content: bytes,
    filename: str,
) -> Tuple[List[str], Dict[str, Any]]:
    """
    Parse un fichier uploadé et retourne (liste de noms, metadata).
    """
    name = (filename or "").lower()
    meta: Dict[str, Any] = {"filename": filename, "format": "unknown"}

    if name.endswith((".csv", ".tsv", ".txt")) or not name:
        return _parse_tabular_or_text(content, name, meta)

    if name.endswith((".xlsx", ".xls")):
        return _parse_excel(content, meta)

    if name.endswith(".json"):
        return _parse_json(content, meta)

    # Texte brut par défaut
    return _parse_plain_text(content, meta)


def _parse_plain_text(content: bytes, meta: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    text = _decode_bytes(content)
    meta["format"] = "text"
    extracted = extract_names_from_text(text, max_names=MAX_BATCH_ROWS)
    names = [n for n, _ in extracted]
    meta["lines_scanned"] = len(text.splitlines())
    return names, meta


def _parse_tabular_or_text(
    content: bytes,
    filename: str,
    meta: Dict[str, Any],
) -> Tuple[List[str], Dict[str, Any]]:
    text = _decode_bytes(content)
    sep = "\t" if filename.endswith(".tsv") else ("," if "," in text.split("\n")[0] else None)

    if sep and filename.endswith((".csv", ".tsv")):
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep, nrows=MAX_BATCH_ROWS)
            return _names_from_dataframe(df, meta)
        except Exception as exc:
            logger.warning("CSV parse failed, fallback text: %s", exc)

    meta["format"] = "text"
    extracted = extract_names_from_text(text, max_names=MAX_BATCH_ROWS)
    return [n for n, _ in extracted], meta


def _parse_excel(content: bytes, meta: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    meta["format"] = "excel"
    df = pd.read_excel(io.BytesIO(content), nrows=MAX_BATCH_ROWS)
    return _names_from_dataframe(df, meta)


def _parse_json(content: bytes, meta: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    import json

    meta["format"] = "json"
    data = json.loads(_decode_bytes(content))
    names: List[str] = []

    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                for key in ("name", "nom", "full_name", "normalized", "input"):
                    if key in item and item[key]:
                        names.append(str(item[key]))
                        break
    elif isinstance(data, dict) and "names" in data:
        names = [str(n) for n in data["names"]]

    return names[:MAX_BATCH_ROWS], meta


def _names_from_dataframe(df: pd.DataFrame, meta: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    meta["format"] = meta.get("format", "tabular")
    meta["rows"] = len(df)
    meta["columns"] = list(df.columns.astype(str))

    headers = [str(c) for c in df.columns]
    col_indices = detect_name_columns(headers)

    names: List[str] = []
    for _, row in df.iterrows():
        for idx in col_indices:
            if idx < len(row):
                val = row.iloc[idx]
                if pd.notna(val):
                    s = str(val).strip()
                    if s and len(s) >= 2:
                        names.append(s)
        if len(names) >= MAX_BATCH_ROWS:
            break

    # Dédupliquer en gardant l'ordre
    seen = set()
    unique: List[str] = []
    for n in names:
        key = n.lower()
        if key not in seen:
            seen.add(key)
            unique.append(n)

    meta["names_extracted"] = len(unique)
    return unique[:MAX_BATCH_ROWS], meta


def _decode_bytes(content: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")
