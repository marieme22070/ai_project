"""In-Context Learning: sélection d'exemples pertinents pour le prompt GPT."""

from typing import Any, Dict, List

from rapidfuzz import fuzz, process

from app.services.name_knowledge import get_all_names, normalize_lookup_key


def select_icl_examples(
    query: str,
    limit: int = 8,
    min_score: float = 55.0,
) -> List[Dict[str, Any]]:
    """
    Sélectionne les entrées du dictionnaire les plus proches du nom saisi
    pour few-shot learning dans le contexte long.
    """
    query_key = normalize_lookup_key(query)
    if not query_key:
        return []

    all_names = get_all_names()
    if not all_names:
        return []

    keys = list(all_names.keys())
    matches = process.extract(
        query_key,
        keys,
        scorer=fuzz.WRatio,
        limit=min(limit * 2, len(keys)),
    )

    examples: List[Dict[str, Any]] = []
    seen_norm = set()

    for key, score, _ in matches:
        if score < min_score:
            continue
        entry = all_names[key]
        norm = entry.get("normalized", "")
        if norm.lower() in seen_norm:
            continue
        seen_norm.add(norm.lower())
        examples.append(
            {
                "input": key,
                "normalized": norm,
                "arabic": entry.get("arabic", ""),
                "relevance_score": round(score, 1),
            }
        )
        if len(examples) >= limit:
            break

    return examples


def format_icl_block(examples: List[Dict[str, Any]]) -> str:
    """Formate les exemples few-shot pour injection dans le prompt."""
    if not examples:
        return ""

    lines = ["Exemples de corrections validées (utilise-les comme référence) :"]
    for ex in examples:
        ar = f" | arabe: {ex['arabic']}" if ex.get("arabic") else ""
        lines.append(f'  • "{ex["input"]}" → "{ex["normalized"]}"{ar}')
    return "\n".join(lines)
