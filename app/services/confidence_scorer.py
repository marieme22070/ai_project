"""Score de confiance unifié pour annotations et normalisation."""

from typing import Any, Dict, Optional


def compute_annotation_scores(
    ai_confidence: int,
    phonetic_score: Optional[float] = None,
    embedding_score: Optional[float] = None,
    duplicate_probability: Optional[float] = None,
    local_match: bool = False,
    ai_used: bool = False,
) -> Dict[str, Any]:
    """
    Calcule confidence, annotation_quality et duplicate_probability agrégés.
    """
    base = float(ai_confidence)

    if phonetic_score is not None:
        base = base * 0.55 + phonetic_score * 0.45

    if embedding_score is not None and embedding_score > 70:
        base = base * 0.7 + embedding_score * 0.3

    if local_match:
        base = min(100.0, base + 8)

    if ai_used:
        base = min(100.0, base + 3)

    confidence = int(round(min(100, max(0, base))))

    # Qualité d'annotation (pour le jury / dashboard)
    quality_factors = [confidence / 100.0]
    if phonetic_score and phonetic_score >= 80:
        quality_factors.append(0.9)
    elif phonetic_score and phonetic_score >= 65:
        quality_factors.append(0.7)
    else:
        quality_factors.append(0.5 if ai_used else 0.4)

    annotation_quality = round(sum(quality_factors) / len(quality_factors) * 100, 1)

    dup_prob = duplicate_probability
    if dup_prob is None:
        dup_prob = 0.0
    dup_prob = round(min(100.0, max(0.0, dup_prob)), 1)

    return {
        "confidence": confidence,
        "annotation_quality": annotation_quality,
        "duplicate_probability": dup_prob,
    }
