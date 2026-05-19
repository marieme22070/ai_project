"""
Reconnaissance vocale specialisee : noms propres mauritaniens uniquement.
Whisper (prompt + temperature=0) → extraction nom → RapidFuzz → dictionnaire local.
"""

import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import fuzz, process

from app.ai.openai_client import get_openai_client
from app.config import get_settings
from app.services.local_dictionary import normalize_from_local_dictionary
from app.services.name_knowledge import get_all_names, normalize_lookup_key

logger = logging.getLogger(__name__)
settings = get_settings()

WHISPER_PROMPT_BASE = "Le fichier contient uniquement un nom mauritanien."
WHISPER_PROMPT_MAX_CHARS = 900


def _auto_correct_threshold() -> int:
    return int(getattr(settings, "voice_auto_correct_threshold", 85))

# Formules parasites (fr / ar) — pas des noms
FILLER_PATTERNS = [
    r"^(je\s+m['\u2019]?appelle|mon\s+nom\s+est|c'est|ce\s+est|il\s+s'appelle|elle\s+s'appelle)\s+",
    r"^(my\s+name\s+is|i\s+am|this\s+is)\s+",
    r"^(اسمي|اسمه|اسمها|هو|هي)\s*",
    r"^(nom|name)\s*[:]\s*",
    r"^(voici|ici)\s+",
]

# Mots entiers a retirer
STOPWORDS = {
    "euh",
    "hein",
    "bonjour",
    "salut",
    "merci",
    "oui",
    "non",
    "alors",
    "donc",
    "voila",
    "voilà",
    "please",
    "the",
    "un",
    "une",
    "le",
    "la",
    "les",
}


def _all_name_keys() -> List[str]:
    return sorted(get_all_names().keys())


def build_whisper_prompt() -> str:
    """Prompt dynamique avec cles ALL_NAMES (tronque si necessaire)."""
    keys = _all_name_keys()
    # Prioriser noms longs (hassaniya compose) et variantes apprises
    keys_by_len = sorted(keys, key=len, reverse=True)

    base = (
        f"{WHISPER_PROMPT_BASE} "
        "Langues: francais, arabe, hassaniya, pulaar, wolof. "
        "Transcrire UNIQUEMENT le nom propre entendu, sans phrase ni ponctuation finale."
    )

    examples = ", ".join(keys_by_len)
    prompt = f"{base} Noms connus: {examples}"
    if len(prompt) > WHISPER_PROMPT_MAX_CHARS:
        trimmed = keys_by_len[:120]
        prompt = f"{base} Noms connus: {', '.join(trimmed)}"
        if len(prompt) > WHISPER_PROMPT_MAX_CHARS:
            prompt = prompt[: WHISPER_PROMPT_MAX_CHARS - 3] + "..."
    return prompt


def extract_proper_name_only(text: str) -> str:
    """Ne garde que le nom propre (un ou plusieurs mots)."""
    if not text:
        return ""

    raw = unicodedata.normalize("NFKC", text.strip())
    raw = raw.strip(".,;:!?\"'«»""''()[]")

    for pattern in FILLER_PATTERNS:
        raw = re.sub(pattern, "", raw, flags=re.IGNORECASE | re.UNICODE)

    # Une seule ligne / premier segment
    raw = raw.split("\n")[0].split(".")[0].split("?")[0].split("!")[0].strip()

    # Retirer guillemets residuels
    raw = raw.strip("'\"")

    words = []
    for w in raw.split():
        w_clean = w.strip(".,;:!?\"'")
        if not w_clean:
            continue
        if w_clean.lower() in STOPWORDS:
            continue
        words.append(w_clean)

    if not words:
        return ""

    # Max 6 mots (noms composes mauritaniens longs)
    return " ".join(words[:6])


def _fuzzy_candidates() -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """Cles + formes normalisees pour matching vocal."""
    names = get_all_names()
    label_to_entry: Dict[str, Dict[str, Any]] = {}
    labels: List[str] = []

    for key, entry in names.items():
        labels.append(key)
        label_to_entry[key] = {**entry, "_match_key": key}
        norm = (entry.get("normalized") or "").strip()
        if norm:
            nk = normalize_lookup_key(norm)
            if nk not in label_to_entry:
                labels.append(nk)
                label_to_entry[nk] = {**entry, "_match_key": key}

    return labels, label_to_entry


def correct_voice_transcription(text: str) -> Dict[str, Any]:
    """
    RapidFuzz sur ALL_NAMES + correction dictionnaire si score > 85.
    """
    extracted = extract_proper_name_only(text)
    if not extracted:
        return {
            "extracted_name": "",
            "corrected_name": "",
            "arabic_name": "",
            "fuzzy_score": 0.0,
            "auto_corrected": False,
            "match_key": None,
            "match_source": "empty",
        }

    key = normalize_lookup_key(extracted)
    labels, label_to_entry = _fuzzy_candidates()

    exact = label_to_entry.get(key)
    if exact:
        return {
            "extracted_name": extracted,
            "corrected_name": exact["normalized"],
            "arabic_name": exact.get("arabic", ""),
            "fuzzy_score": 100.0,
            "auto_corrected": True,
            "match_key": exact.get("_match_key", key),
            "match_source": "exact",
        }

    match = process.extractOne(key, labels, scorer=fuzz.WRatio)
    if not match:
        local = normalize_from_local_dictionary(extracted)
        score = float(local.get("confidence", 0))
        return {
            "extracted_name": extracted,
            "corrected_name": local["normalized"],
            "arabic_name": local.get("arabic_name", ""),
            "fuzzy_score": score,
            "auto_corrected": score >= _auto_correct_threshold(),
            "match_key": local.get("matched_key"),
            "match_source": local.get("local_source", "local_dictionary"),
        }

    matched_label, score, _ = match
    entry = label_to_entry[matched_label]
    auto = float(score) >= _auto_correct_threshold()

    return {
        "extracted_name": extracted,
        "corrected_name": entry["normalized"] if auto else extracted,
        "arabic_name": entry.get("arabic", "") if auto else "",
        "fuzzy_score": float(score),
        "auto_corrected": auto,
        "match_key": entry.get("_match_key", matched_label),
        "match_source": "rapidfuzz" if auto else "low_confidence",
    }


async def transcribe_mauritanian_name(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    language_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Whisper specialise noms mauritaniens.
    language_hint: fr, ar, hassaniya, pulaar, wolof (fr/ar pour Whisper ISO).
    """
    from openai import APIConnectionError, APIStatusError, RateLimitError

    client = get_openai_client()
    if client is None:
        raise ValueError(
            "Cle OpenAI manquante. Configurez OPENAI_API_KEY dans .env pour Whisper."
        )

    if not audio_bytes or len(audio_bytes) < 100:
        raise ValueError("Enregistrement audio trop court ou vide.")

    safe_name = filename if "." in filename else f"{filename}.webm"
    prompt = build_whisper_prompt()

    hint = (language_hint or "").lower().strip()
    languages: List[Optional[str]]
    if hint in ("ar", "arabic", "arabe"):
        languages = ["ar", "fr"]
    elif hint in ("fr", "french", "francais", "français", "hassaniya", "pulaar", "wolof"):
        languages = ["fr", "ar"]
    else:
        languages = ["fr", "ar"]

    best: Optional[Dict[str, Any]] = None

    def _run_whisper(lang: str) -> Tuple[str, Dict[str, Any]]:
        response = client.audio.transcriptions.create(
            model=settings.openai_model_whisper,
            file=(safe_name, audio_bytes, "audio/webm"),
            language=lang,
            temperature=float(getattr(settings, "whisper_temperature", 0)),
            prompt=prompt,
        )
        whisper_text = (response.text or "").strip()
        if not whisper_text:
            raise ValueError("Whisper n'a pas reconnu de nom dans l'audio.")
        correction = correct_voice_transcription(whisper_text)
        correction["whisper_raw"] = whisper_text
        correction["whisper_language"] = lang
        return whisper_text, correction

    try:
        for i, lang in enumerate(languages):
            whisper_text, correction = _run_whisper(lang)
            if best is None or correction["fuzzy_score"] > best["fuzzy_score"]:
                best = {
                    **correction,
                    "transcription": whisper_text,
                }
            if correction["fuzzy_score"] >= _auto_correct_threshold():
                break
            if i == 0 and len(languages) > 1:
                logger.info(
                    "Whisper %s score %.1f < %s, essai %s",
                    lang,
                    correction["fuzzy_score"],
                    _auto_correct_threshold(),
                    languages[1],
                )

        if best is None:
            raise ValueError("Whisper n'a pas reconnu de nom dans l'audio.")

        return best

    except RateLimitError as exc:
        raise ValueError(
            "Compte OpenAI inactif ou quota depasse. "
            "Activez la facturation sur platform.openai.com."
        ) from exc
    except APIStatusError as exc:
        if exc.status_code == 429:
            raise ValueError(
                "Facturation OpenAI inactive (erreur 429). "
                "Impossible d'utiliser Whisper tant que le compte n'est pas active."
            ) from exc
        raise ValueError(f"Erreur API Whisper: {exc.message}") from exc
    except APIConnectionError as exc:
        raise ValueError("Connexion a OpenAI impossible.") from exc


async def process_voice_to_name(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    language_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Pipeline vocal complet : Whisper → nom seul → RapidFuzz → dictionnaire (seuil 85).
    """
    voice = await transcribe_mauritanian_name(audio_bytes, filename, language_hint)
    extracted = voice.get("extracted_name") or extract_proper_name_only(voice.get("transcription", ""))

    if voice.get("auto_corrected"):
        local = normalize_from_local_dictionary(voice["corrected_name"])
        return {
            "input": extracted,
            "transcription": voice.get("transcription", ""),
            "normalized": voice["corrected_name"],
            "arabic_name": voice.get("arabic_name") or local.get("arabic_name", ""),
            "confidence": min(100, int(voice["fuzzy_score"])),
            "variants": list(
                dict.fromkeys(
                    [
                        extracted,
                        voice.get("transcription", ""),
                        voice["corrected_name"],
                        voice.get("whisper_raw", ""),
                    ]
                )
            )[:8],
            "metadata": {
                "source": "voice",
                "voice_pipeline": "mauritanian_names_only",
                "whisper_language": voice.get("whisper_language"),
                "whisper_prompt": WHISPER_PROMPT_BASE,
                "whisper_temperature": 0,
                "fuzzy_score": voice.get("fuzzy_score"),
                "auto_corrected": True,
                "match_key": voice.get("match_key"),
                "match_source": voice.get("match_source"),
                "local_source": local.get("local_source"),
                "ai_used": False,
            },
        }

    local = normalize_from_local_dictionary(extracted or voice.get("transcription", ""))
    return {
        "input": extracted or voice.get("transcription", ""),
        "transcription": voice.get("transcription", ""),
        "normalized": local["normalized"],
        "arabic_name": local.get("arabic_name", ""),
        "confidence": local.get("confidence", 70),
        "variants": local.get("variants", [])[:8],
        "metadata": {
            "source": "voice",
            "voice_pipeline": "mauritanian_names_only",
            "whisper_language": voice.get("whisper_language"),
            "fuzzy_score": voice.get("fuzzy_score"),
            "auto_corrected": False,
            "match_source": voice.get("match_source"),
            "local_source": local.get("local_source"),
            "notes": local.get("notes", ""),
            "ai_used": False,
        },
    }
