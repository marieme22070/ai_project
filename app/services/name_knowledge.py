"""
Fusion LOCAL_NAMES + LEARNED_NAMES, sauvegarde auto et rechargement a chaud.
"""

import importlib
import logging
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

from app.data import learned_names as learned_names_module
from app.data.local_names import LOCAL_NAMES

logger = logging.getLogger(__name__)

LEARNED_FILE = Path(__file__).resolve().parent.parent / "data" / "learned_names.py"
_file_lock = Lock()


def normalize_lookup_key(text: str) -> str:
    text = unicodedata.normalize("NFKC", text.strip().lower())
    return re.sub(r"\s+", " ", text)


def reload_learned_names() -> Dict[str, Dict[str, Any]]:
    """Recharge learned_names.py sans redemarrer le serveur."""
    importlib.reload(learned_names_module)
    learned = getattr(learned_names_module, "LEARNED_NAMES", {}) or {}
    logger.info("LEARNED_NAMES recharge: %d entrees", len(learned))
    return learned


def get_learned_names() -> Dict[str, Dict[str, Any]]:
    return getattr(learned_names_module, "LEARNED_NAMES", {}) or {}


def get_all_names() -> Dict[str, Dict[str, Any]]:
    """LEARNED_NAMES ecrase LOCAL_NAMES sur les memes cles."""
    return {**LOCAL_NAMES, **get_learned_names()}


def format_knowledge_for_prompt(max_lines: int = 200) -> str:
    """Format compact pour le system prompt GPT."""
    all_names = get_all_names()
    lines = []
    for key in sorted(all_names.keys()):
        entry = all_names[key]
        norm = entry.get("normalized", "")
        ar = entry.get("arabic", "")
        suffix = f" ({ar})" if ar else ""
        lines.append(f"- {key} → {norm}{suffix}")
        if len(lines) >= max_lines:
            lines.append(f"... et {len(all_names) - max_lines} autres entrees")
            break
    return "\n".join(lines) if lines else "(aucune entree)"


def _escape_py_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _format_learned_file(data: Dict[str, Dict[str, Any]]) -> str:
    lines = [
        '"""',
        "Corrections apprises — validees par un administrateur.",
        "Genere automatiquement — ne pas editer manuellement pendant une validation.",
        '"""',
        "",
        "LEARNED_NAMES: dict = {",
    ]
    for key in sorted(data.keys()):
        entry = data[key]
        norm = _escape_py_string(str(entry.get("normalized", "")))
        ar = _escape_py_string(str(entry.get("arabic", "")))
        by = _escape_py_string(str(entry.get("learned_by", "admin")))
        at = _escape_py_string(str(entry.get("learned_at", "")))
        lines.append(f'    "{_escape_py_string(key)}": {{')
        lines.append(f'        "normalized": "{norm}",')
        lines.append(f'        "arabic": "{ar}",')
        lines.append(f'        "learned_by": "{by}",')
        lines.append(f'        "learned_at": "{at}",')
        lines.append("    },")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def save_learned_name(
    input_key: str,
    normalized: str,
    arabic: str = "",
    learned_by: str = "admin",
) -> Dict[str, Any]:
    """
    Ajoute ou met a jour une correction dans learned_names.py et recharge le module.
    """
    key = normalize_lookup_key(input_key)
    if not key or not normalized.strip():
        raise ValueError("Cle ou nom normalise invalide")

    entry = {
        "normalized": normalized.strip(),
        "arabic": (arabic or "").strip(),
        "learned_by": learned_by,
        "learned_at": datetime.now(timezone.utc).isoformat(),
    }

    with _file_lock:
        current = dict(get_learned_names())
        current[key] = entry
        LEARNED_FILE.parent.mkdir(parents=True, exist_ok=True)
        LEARNED_FILE.write_text(_format_learned_file(current), encoding="utf-8")
        reload_learned_names()

    logger.info("Correction apprise sauvegardee: %s -> %s", key, normalized)
    return {"key": key, **entry}


def get_knowledge_stats() -> Dict[str, int]:
    learned = get_learned_names()
    all_names = get_all_names()
    return {
        "local_count": len(LOCAL_NAMES),
        "learned_count": len(learned),
        "total_count": len(all_names),
    }
