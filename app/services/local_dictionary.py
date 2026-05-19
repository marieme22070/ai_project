"""Normalisation via dictionnaire local (LOCAL + LEARNED) + RapidFuzz."""

import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import fuzz, process

from app.data.local_names import FUZZY_EXACT, FUZZY_HIGH, FUZZY_MEDIUM
from app.services.name_knowledge import get_all_names

logger = logging.getLogger(__name__)


def _names_dict() -> Dict[str, Dict[str, str]]:
    return get_all_names()


def _keys() -> List[str]:
    return list(_names_dict().keys())


def _normalize_key(text: str) -> str:
    text = unicodedata.normalize("NFKC", text.strip().lower())
    text = re.sub(r"\s+", " ", text)
    return text


def _lookup_exact(key: str) -> Optional[Dict[str, str]]:
    return _names_dict().get(key)


def _fuzzy_lookup(key: str) -> Optional[Tuple[Dict[str, str], float, str]]:
    names = _names_dict()
    keys = list(names.keys())
    if not key or not keys:
        return None
    match = process.extractOne(key, keys, scorer=fuzz.WRatio, score_cutoff=FUZZY_MEDIUM)
    if not match:
        return None
    matched_key, score, _ = match
    return names[matched_key], float(score), matched_key


def _correct_word(word: str) -> Tuple[str, Optional[str], float]:
    key = _normalize_key(word)
    if not key:
        return word, None, 0.0

    exact = _lookup_exact(key)
    if exact:
        return exact["normalized"], exact["arabic"], 100.0

    fuzzy = _fuzzy_lookup(key)
    if fuzzy:
        entry, score, _ = fuzzy
        return entry["normalized"], entry["arabic"], score

    return word, None, 50.0


def normalize_from_local_dictionary(name: str) -> Dict[str, Any]:
    raw = name.strip()
    key_full = _normalize_key(raw)
    variants: List[str] = [raw]
    notes_parts: List[str] = []

    from app.services.name_knowledge import get_learned_names

    if key_full in get_learned_names():
        notes_parts.append("learned")

    exact = _lookup_exact(key_full)
    if exact:
        source = "learned_exact" if key_full in get_learned_names() else "local_exact"
        return _build_result(
            raw,
            exact["normalized"],
            exact["arabic"],
            98 if source.startswith("learned") else 97,
            variants + [exact["normalized"], key_full],
            source,
            matched_key=key_full,
        )

    fuzzy_full = _fuzzy_lookup(key_full)
    if fuzzy_full and fuzzy_full[1] >= FUZZY_HIGH:
        entry, score, matched_key = fuzzy_full
        source = "learned_fuzzy" if matched_key in get_learned_names() else "local_fuzzy"
        return _build_result(
            raw,
            entry["normalized"],
            entry["arabic"],
            min(97, int(score)),
            variants + [entry["normalized"], matched_key],
            source,
            matched_key=matched_key,
        )

    words = raw.split()
    corrected: List[str] = []
    arabic_parts: List[str] = []
    scores: List[float] = []

    for word in words:
        norm, ar, sc = _correct_word(word)
        corrected.append(norm)
        if ar:
            arabic_parts.append(ar)
        scores.append(sc)
        variants.append(norm)

    normalized = " ".join(corrected)
    arabic_name = " ".join(arabic_parts) if arabic_parts else ""

    assembled_key = _normalize_key(normalized)
    exact2 = _lookup_exact(assembled_key)
    if exact2:
        normalized = exact2["normalized"]
        arabic_name = exact2["arabic"]
        scores.append(97)

    avg_score = sum(scores) / len(scores) if scores else 70
    changed = _normalize_key(normalized) != key_full
    confidence = int(min(95, avg_score + (10 if changed else 0)))

    if fuzzy_full and fuzzy_full[1] >= FUZZY_MEDIUM and not changed:
        entry, score, mk = fuzzy_full
        normalized = entry["normalized"]
        arabic_name = entry["arabic"]
        confidence = min(94, int(score))
        notes_parts.append(f"fuzzy:{mk}")

    note = ", ".join(notes_parts) if notes_parts else "dictionnaire fusionne"
    return _build_result(
        raw,
        normalized,
        arabic_name,
        confidence,
        list(dict.fromkeys(variants + [normalized])),
        "merged_word_fuzzy",
        notes=note,
    )


def _build_result(
    raw: str,
    normalized: str,
    arabic: str,
    confidence: int,
    variants: List[str],
    source: str,
    matched_key: Optional[str] = None,
    notes: str = "",
) -> Dict[str, Any]:
    return {
        "normalized": normalized,
        "arabic_name": arabic,
        "confidence": confidence,
        "variants": variants[:10],
        "language_detected": "fr",
        "notes": notes or source,
        "ai_used": False,
        "model": "local_dictionary",
        "local_source": source,
        "matched_key": matched_key,
    }
