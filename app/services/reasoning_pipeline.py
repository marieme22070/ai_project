"""Pipeline de raisonnement N-ID en 6 étapes (exécution locale)."""

from typing import Any, Dict, List, Optional

from app.ai.annotation_prompts import PIPELINE_STEPS
from app.services.entity_extractor import extract_names_from_text, linguistic_hint
from app.services.phonetic import combined_match_score
from app.utils.arabic import is_arabic


def _step_explanation(
    original: str,
    normalized: str,
    language: str,
    phonetic: float,
    group_id: str,
    uncertain: bool,
) -> str:
    parts = [
        f"[1-Extraction] Entité extraite du document : « {original} ».",
        f"[2-Normalisation] Forme standard : « {normalized} ».",
        f"[3-Linguistique] Langue détectée : {language}.",
        f"[4-Phonétique] Similarité original/normalisé : {phonetic:.0f}%.",
    ]
    if group_id:
        parts.append(
            f"[5-Regroupement] Assigné au cluster {group_id} (variantes probablement identiques)."
        )
    elif uncertain:
        parts.append(
            "[5-Regroupement] Non fusionné — incertitude élevée, conservé comme entité distincte."
        )
    else:
        parts.append("[5-Regroupement] Aucun doublon probable détecté dans le document.")
    parts.append("[6-Explication] Décision basée uniquement sur le texte source.")
    return " ".join(parts)


def apply_six_step_pipeline(
    text: str,
    annotations: List[Dict[str, Any]],
    clusters_raw: List[Dict[str, Any]],
    cluster_threshold: float = 88.0,
) -> Dict[str, Any]:
    """
    Enrichit les entités avec explications structurées selon les 6 étapes.
    Ne fusionne que si score >= cluster_threshold (précision > quantité).
    """
    norm_to_group: Dict[str, str] = {}
    duplicate_clusters: List[Dict[str, Any]] = []

    for idx, cluster in enumerate(clusters_raw, start=1):
        avg = float(cluster.get("avg_similarity", 0))
        if avg < cluster_threshold:
            continue
        gid = f"G{idx}"
        members = cluster.get("variants") or [cluster.get("canonical", "")]
        for m in members:
            norm_to_group[m.lower().strip()] = gid
        duplicate_clusters.append(
            {
                "group_id": gid,
                "members": members,
                "reasoning": (
                    f"[5-Regroupement] Fusion justifiée (similarité moyenne {avg:.0f}%). "
                    f"Variantes : {', '.join(f'«{x}»' for x in members)}. "
                    f"[6-Explication] Translittération ou erreur orthographique probable ; "
                    f"forme canonique : « {cluster.get('canonical', '')} »."
                ),
            }
        )

    enriched_entities: List[Dict[str, Any]] = []

    for ann in annotations:
        if ann.get("error"):
            continue
        original = ann.get("input") or ann.get("detected_name", "")
        normalized = ann.get("normalized") or original
        meta = ann.get("metadata") or {}
        lang = meta.get("language_detected") or linguistic_hint(original)
        if is_arabic(original) and lang == "fr":
            lang = "ar"

        phon = ann.get("phonetic_score")
        if phon is None:
            phon = combined_match_score(original, normalized)

        orig_key = original.lower().strip()
        norm_key = normalized.lower().strip()
        group_id = norm_to_group.get(orig_key) or norm_to_group.get(norm_key) or ""

        uncertain = False
        if not group_id:
            for other in annotations:
                if other is ann or other.get("error"):
                    continue
                other_orig = other.get("input") or ""
                score = combined_match_score(original, other_orig)
                if 75 <= score < cluster_threshold:
                    uncertain = True
                    break

        conf = float(ann.get("confidence") or 0)
        if uncertain:
            conf = min(conf, 72)

        explanation = _step_explanation(
            original, normalized, lang, phon, group_id, uncertain
        )

        enriched_entities.append(
            {
                "original": original,
                "normalized": normalized,
                "language_detected": lang,
                "confidence_score": int(conf),
                "phonetic_similarity": round(float(phon), 1),
                "duplicate_group_id": group_id,
                "explanation": explanation,
            }
        )

    return {
        "entities": enriched_entities,
        "duplicate_clusters": duplicate_clusters,
        "pipeline_steps_applied": PIPELINE_STEPS,
    }
