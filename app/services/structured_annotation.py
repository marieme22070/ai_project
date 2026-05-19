"""Assemblage du format JSON structuré d'annotation (production + fallback local)."""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from openai import APIConnectionError, APIStatusError, RateLimitError

from app.ai.annotation_prompts import (
    DOCUMENT_ANNOTATION_SYSTEM,
    DOCUMENT_ANNOTATION_USER_TEMPLATE,
    N_ID_TAGLINE,
    PIPELINE_STEPS,
)
from app.services.reasoning_pipeline import apply_six_step_pipeline
from app.ai.openai_client import get_openai_client
from app.config import get_settings
from app.services.duplicate_detector import find_identity_clusters
from app.services.icl_selector import format_icl_block, select_icl_examples
from app.services.phonetic import combined_match_score
from app.utils.arabic import is_arabic

logger = logging.getLogger(__name__)
settings = get_settings()


def _detect_language(name: str, meta_lang: Optional[str] = None) -> str:
    if meta_lang:
        return meta_lang
    if is_arabic(name):
        return "ar"
    lower = name.lower()
    if any(x in lower for x in ("ould", "oul", "wal", "mohamed", "mouhamed")):
        return "hassaniya"
    if any(x in lower for x in ("diallo", "ndiaye", "coulibaly", "traore", "sall")):
        return "pulaar|wolof|mixed"
    return "fr"


def _phonetic_similarity(original: str, normalized: str) -> float:
    if not original or not normalized:
        return 0.0
    return round(combined_match_score(original, normalized), 1)


def build_structured_from_annotations(
    text: str,
    annotations: List[Dict[str, Any]],
    clusters_raw: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Construit le JSON obligatoire via le pipeline local en 6 étapes."""
    pipeline_result = apply_six_step_pipeline(text, annotations, clusters_raw)
    entities = pipeline_result["entities"]
    duplicate_clusters = pipeline_result["duplicate_clusters"]

    confidences = [e["confidence_score"] for e in entities]
    overall = round(sum(confidences) / len(confidences), 1) if confidences else 0.0

    dup_count = len(duplicate_clusters)
    entity_count = len(entities)
    uncertain_count = sum(1 for e in entities if "incertitude" in e.get("explanation", "").lower())

    summary = (
        f"[Pipeline 6 étapes] {entity_count} entité(s) extraite(s) du document. "
        f"{dup_count} regroupement(s) confirmé(s) (seuil ≥88%). "
        f"Confiance moyenne {overall:.0f}%. "
    )
    if uncertain_count:
        summary += f"{uncertain_count} entité(s) laissée(s) distincte(s) par prudence (anti-fusion forcée). "
    if dup_count:
        summary += "Variantes multilingues (arabe/latin/hassaniya) regroupées."

    return {
        "entities": entities,
        "duplicate_clusters": duplicate_clusters,
        "document_summary": summary.strip(),
        "overall_quality_score": min(100, int(round(overall))),
        "metadata": {
            "pipeline_steps": PIPELINE_STEPS,
            "tagline": N_ID_TAGLINE,
        },
    }


def _parse_json_response(content: str) -> Dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\n?", "", content)
        content = re.sub(r"\n?```$", "", content)
    return json.loads(content)


def _find_grounded_original(original: str, local_by_orig: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """Retrouve la clé locale correspondant à un original (exact ou phonétique)."""
    key = original.lower().strip()
    if key in local_by_orig:
        return key
    for k in local_by_orig:
        if combined_match_score(original, k) >= 88:
            return k
    return None


def _is_known_name(name: str, known_originals: set[str]) -> bool:
    key = name.lower().strip()
    if key in known_originals:
        return True
    for k in known_originals:
        if combined_match_score(name, k) >= 88:
            return True
    return False


def _filter_clusters_to_known(
    clusters: List[Dict[str, Any]],
    known_originals: set[str],
) -> List[Dict[str, Any]]:
    """Ne garde que les membres de clusters présents dans le document."""
    filtered = []
    for cluster in clusters:
        members = cluster.get("members") or []
        valid = [m for m in members if _is_known_name(m, known_originals)]
        if len(valid) >= 2:
            filtered.append({**cluster, "members": valid})
    return filtered


def _merge_gpt_with_local(
    gpt: Dict[str, Any],
    local: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Fusion : enrichissement GPT sur entités extraites localement uniquement.
    Rejette toute entité inventée absente du pipeline local.
    """
    local_entities = local.get("entities", [])
    local_by_orig = {e["original"].lower().strip(): e for e in local_entities}
    known_keys = set(local_by_orig.keys())

    merged_entities: List[Dict[str, Any]] = []
    gpt_entities = gpt.get("entities") or []

    for ge in gpt_entities:
        orig = (ge.get("original") or "").strip()
        grounded_key = _find_grounded_original(orig, local_by_orig) if orig else None
        if not grounded_key:
            continue
        base = local_by_orig[grounded_key]
        canonical_orig = base.get("original", orig)
        normalized = ge.get("normalized") or base.get("normalized", canonical_orig)
        merged_entities.append(
            {
                "original": canonical_orig,
                "normalized": normalized,
                "language_detected": ge.get("language_detected")
                or base.get("language_detected", "fr"),
                "confidence_score": int(
                    ge.get("confidence_score") or base.get("confidence_score", 0)
                ),
                "phonetic_similarity": float(
                    ge.get("phonetic_similarity")
                    or base.get("phonetic_similarity", 0)
                    or _phonetic_similarity(canonical_orig, normalized)
                ),
                "duplicate_group_id": ge.get("duplicate_group_id")
                or base.get("duplicate_group_id", ""),
                "explanation": ge.get("explanation") or base.get("explanation", ""),
            }
        )

    seen = {e["original"].lower().strip() for e in merged_entities}
    for le in local_entities:
        key = le["original"].lower().strip()
        if key not in seen:
            merged_entities.append(le)

    if not merged_entities:
        merged_entities = local_entities

    gpt_clusters = _filter_clusters_to_known(gpt.get("duplicate_clusters") or [], known_keys)
    clusters = gpt_clusters if gpt_clusters else local.get("duplicate_clusters", [])

    meta = local.get("metadata") or {}
    meta.update(
        {
            "engine": "openai+local",
            "ai_used": True,
            "entities_grounded": len(merged_entities),
            "gpt_entities_rejected": max(0, len(gpt_entities) - len(merged_entities)),
            "pipeline_steps": PIPELINE_STEPS,
        }
    )

    return {
        "entities": merged_entities,
        "duplicate_clusters": clusters,
        "document_summary": gpt.get("document_summary") or local.get("document_summary", ""),
        "overall_quality_score": int(
            gpt.get("overall_quality_score") or local.get("overall_quality_score", 0)
        ),
        "metadata": meta,
    }


def _format_extracted_hint(annotations: List[Dict[str, Any]]) -> str:
    """Liste des noms extraits pour contraindre le modèle (anti-hallucination)."""
    names = []
    for ann in annotations:
        if ann.get("error"):
            continue
        orig = ann.get("input") or ann.get("detected_name", "")
        norm = ann.get("normalized", "")
        if orig:
            names.append(f'- "{orig}" → normalisé local: "{norm}"')
    return "\n".join(names) if names else "(aucune entité extraite)"


async def annotate_document_structured(
    text: str,
    annotations: List[Dict[str, Any]],
    clusters_raw: List[Dict[str, Any]],
    icl_sample_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Produit le JSON structuré obligatoire.
    OpenAI pour raisonnement global long contexte ; fallback pipeline local.
    """
    local = build_structured_from_annotations(text, annotations, clusters_raw)

    client = get_openai_client()
    if client is None:
        meta = local.get("metadata") or {}
        meta.update({"engine": "local", "ai_used": False})
        local["metadata"] = meta
        return local

    # ICL : exemples basés sur le premier nom ou un échantillon
    sample = icl_sample_name or ""
    if not sample and annotations:
        sample = annotations[0].get("input", "")
    icl_examples = format_icl_block(select_icl_examples(sample or "mohamed", limit=12))

    # Tronquer texte très long pour le modèle (garder début + fin)
    input_text = text
    max_chars = 28000
    if len(input_text) > max_chars:
        half = max_chars // 2
        input_text = (
            input_text[:half]
            + "\n\n[... section tronquée pour limite contexte — analyse locale complète sur entités extraites ...]\n\n"
            + input_text[-half:]
        )

    extracted_hint = _format_extracted_hint(annotations)

    user_prompt = DOCUMENT_ANNOTATION_USER_TEMPLATE.format(
        icl_examples=icl_examples or "(aucun exemple ICL)",
        extracted_entities_hint=extracted_hint,
        input_text=input_text,
    )

    model = settings.openai_model_complex if len(text) > 2000 else settings.openai_model_correction

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": DOCUMENT_ANNOTATION_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        gpt_data = _parse_json_response(content)
        return _merge_gpt_with_local(gpt_data, local)
    except (RateLimitError, APIStatusError, APIConnectionError, json.JSONDecodeError) as exc:
        logger.warning("Structured GPT annotation fallback to local: %s", exc)
        local["metadata"] = {"engine": "local", "ai_used": False, "gpt_error": str(exc)[:200]}
        return local
    except Exception as exc:
        logger.error("Structured annotation failed: %s", exc)
        local["metadata"] = {"engine": "local", "ai_used": False, "gpt_error": str(exc)[:200]}
        return local
