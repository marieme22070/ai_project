"""Détection de doublons d'identité — profils et annotations."""

from typing import Any, Dict, List, Set, Tuple

from app.services.phonetic import combined_match_score, find_best_matches


def duplicate_probability_for_name(
    name: str,
    candidates: List[str],
    threshold: float = 78.0,
) -> Tuple[float, List[Dict[str, Any]]]:
    """
    Probabilité qu'un nom soit un doublon d'un candidat existant.
    Retourne (probabilité 0-100, liste des matches proches).
    """
    if not name or not candidates:
        return 0.0, []

    matches = find_best_matches(name, candidates, limit=5, threshold=threshold - 10)
    if not matches:
        return 0.0, []

    top_score = matches[0][1]
    # Mapper score matching → probabilité doublon
    if top_score >= 95:
        prob = min(99.0, top_score)
    elif top_score >= 85:
        prob = top_score * 0.95
    elif top_score >= threshold:
        prob = top_score * 0.75
    else:
        prob = 0.0

    near = [
        {"name": m[0], "similarity_score": m[1], "likely_duplicate": m[1] >= threshold}
        for m in matches
    ]
    return round(prob, 1), near


def find_identity_clusters(
    names: List[str],
    threshold: float = 88.0,
) -> List[Dict[str, Any]]:
    """
    Regroupe des noms d'un même document qui semblent être la même identité.
    """
    clusters: List[Dict[str, Any]] = []
    assigned: Set[int] = set()

    for i, n1 in enumerate(names):
        if i in assigned:
            continue
        group = [i]
        for j, n2 in enumerate(names):
            if j <= i or j in assigned:
                continue
            score = combined_match_score(n1, n2)
            if score >= threshold:
                group.append(j)
                assigned.add(j)

        if len(group) > 1:
            assigned.update(group)
            cluster_names = [names[k] for k in group]
            clusters.append(
                {
                    "canonical": cluster_names[0],
                    "variants": cluster_names,
                    "count": len(cluster_names),
                    "avg_similarity": round(
                        sum(
                            combined_match_score(cluster_names[0], n)
                            for n in cluster_names[1:]
                        )
                        / max(1, len(cluster_names) - 1),
                        1,
                    ),
                }
            )

    return clusters


def detect_citizen_duplicates_enhanced(
    citizens: List[Any],
    threshold: float = 85.0,
) -> List[Dict[str, Any]]:
    """Détection enrichie avec explication et score phonétique."""
    duplicates = []
    seen: Set[Tuple[str, str]] = set()

    for i, c1 in enumerate(citizens):
        names1 = [c1.official_name] + (c1.variants or [])
        for c2 in citizens[i + 1 :]:
            pair_key = tuple(sorted([str(c1.id), str(c2.id)]))
            if pair_key in seen:
                continue

            best_score = 0.0
            best_pair = ("", "")
            names2 = [c2.official_name] + (c2.variants or [])

            for n1 in names1:
                for n2 in names2:
                    score = combined_match_score(n1, n2)
                    if score > best_score:
                        best_score = score
                        best_pair = (n1, n2)

            if best_score >= threshold:
                seen.add(pair_key)
                duplicates.append(
                    {
                        "citizen_1": {
                            "id": str(c1.id),
                            "name": c1.official_name,
                            "arabic_name": getattr(c1, "arabic_name", None),
                        },
                        "citizen_2": {
                            "id": str(c2.id),
                            "name": c2.official_name,
                            "arabic_name": getattr(c2, "arabic_name", None),
                        },
                        "similarity_score": best_score,
                        "duplicate_probability": min(99.0, best_score * 0.98),
                        "matched_variant_pair": list(best_pair),
                        "recommendation": "merge_review"
                        if best_score >= 92
                        else "manual_review",
                        "ai_explanation": _explain_duplicate(best_pair[0], best_pair[1], best_score),
                    }
                )

    return sorted(duplicates, key=lambda x: x["similarity_score"], reverse=True)


def _explain_duplicate(n1: str, n2: str, score: float) -> str:
    if score >= 95:
        return (
            f"Identités très probablement identiques : « {n1} » et « {n2} » "
            f"(similarité {score:.0f}%, variantes phonétiques ou orthographiques)."
        )
    if score >= 85:
        return (
            f"Doublon probable : « {n1} » ↔ « {n2} » "
            f"(score {score:.0f}%). Vérification humaine recommandée."
        )
    return f"Similarité modérée ({score:.0f}%) entre « {n1} » et « {n2} »."
