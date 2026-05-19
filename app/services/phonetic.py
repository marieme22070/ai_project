"""Phonetic and fuzzy matching for Mauritanian names."""

import re
from typing import Dict, List, Tuple

from rapidfuzz import fuzz, process

from app.utils.text import clean_name_for_matching, strip_diacritics

# Phonetic equivalences common in Mauritania / West Africa
PHONETIC_EQUIVALENCES = {
    "ph": "f",
    "kh": "k",
    "gh": "g",
    "ou": "u",
    "ee": "i",
    "ou": "u",
    "ey": "e",
    "ai": "e",
    "ou": "u",
}

VOWEL_MAP = {"a": "0", "e": "0", "i": "0", "o": "0", "u": "0", "y": "0"}
CONSONANT_COLLAPSE = [
    (r"dj", "j"),
    (r"nd", "n"),
    (r"ng", "n"),
    (r"ll", "l"),
    (r"tt", "t"),
    (r"bb", "b"),
    (r"mm", "m"),
    (r"nn", "n"),
]


def african_soundex(name: str) -> str:
    """
    Custom Soundex adapted for West African / Mauritanian names.
    Handles Diallo/Jallo, Mohamed/Muhamed, Ba/Bah, etc.
    """
    text = clean_name_for_matching(name)
    if not text:
        return ""

    text = strip_diacritics(text).lower()
    text = re.sub(r"['\-]", "", text)

    for old, new in PHONETIC_EQUIVALENCES.items():
        text = text.replace(old, new)

    for pattern, repl in CONSONANT_COLLAPSE:
        text = re.sub(pattern, repl, text)

    # Normalize common letter swaps
    text = text.replace("v", "b").replace("w", "u")
    text = re.sub(r"h$", "", text)  # trailing h: bah -> ba
    text = re.sub(r"^mu", "mo", text)  # muhamed -> mohamed

    code = []
    prev = ""
    for char in text:
        if char in VOWEL_MAP:
            mapped = "0"
        elif char.isalpha():
            mapped = char
        else:
            continue
        if mapped != prev:
            code.append(mapped)
            prev = mapped

    key = "".join(code).replace("0", "")[:8]
    return key or text[:6]


def levenshtein_ratio(a: str, b: str) -> float:
    return fuzz.ratio(clean_name_for_matching(a), clean_name_for_matching(b))


def token_sort_ratio(a: str, b: str) -> float:
    return fuzz.token_sort_ratio(clean_name_for_matching(a), clean_name_for_matching(b))


def phonetic_ratio(a: str, b: str) -> float:
    sa = african_soundex(a)
    sb = african_soundex(b)
    if sa == sb and sa:
        return 100.0
    return fuzz.ratio(sa, sb)


def combined_match_score(query: str, candidate: str) -> float:
    scores = [
        levenshtein_ratio(query, candidate) * 0.35,
        token_sort_ratio(query, candidate) * 0.30,
        phonetic_ratio(query, candidate) * 0.35,
    ]
    return round(sum(scores), 2)


def find_best_matches(
    query: str,
    candidates: List[str],
    limit: int = 5,
    threshold: float = 70.0,
) -> List[Tuple[str, float]]:
    if not candidates:
        return []

    scored = []
    for candidate in candidates:
        score = combined_match_score(query, candidate)
        if score >= threshold:
            scored.append((candidate, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


def fuzzy_search_in_list(
    query: str,
    items: List[Dict],
    name_key: str = "official_name",
    limit: int = 10,
) -> List[Dict]:
    names = [item[name_key] for item in items]
    results = process.extract(
        query,
        names,
        scorer=fuzz.WRatio,
        limit=limit,
    )
    output = []
    for match_name, score, idx in results:
        item = items[idx].copy()
        item["score"] = score
        item["phonetic_score"] = phonetic_ratio(query, match_name)
        output.append(item)
    return output
