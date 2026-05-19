import json
import logging
import re
from typing import Any, Dict, Optional

from openai import APIConnectionError, APIStatusError, RateLimitError

from app.ai.openai_client import get_openai_client
from app.ai.prompts import COMPLEX_CASE_PROMPT, build_system_prompt, USER_PROMPT_TEMPLATE
from app.config import get_settings
from app.data.local_names import FUZZY_HIGH
from app.services.fallback_rules import apply_fallback_normalization
from app.services.local_dictionary import normalize_from_local_dictionary
from app.utils.text import title_case_name

logger = logging.getLogger(__name__)
settings = get_settings()

COMPLEX_PATTERNS = [
    r"N'[A-Z]",
    r"\d",
    r"[^\w\s'-]{2,}",
    r"\b(EL|AL|IBN|OUL|WAL)\b",
]


def _is_complex_case(name: str) -> bool:
    upper = name.upper()
    for pattern in COMPLEX_PATTERNS:
        if re.search(pattern, upper if "N'" in pattern else name, re.IGNORECASE):
            return True
    return len(name.split()) > 4


def _parse_json_response(content: str) -> Dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\n?", "", content)
        content = re.sub(r"\n?```$", "", content)
    return json.loads(content)


def _merge_local_and_ai(local: Dict[str, Any], ai: Dict[str, Any], original: str) -> Dict[str, Any]:
    """Priorité au dictionnaire local si score élevé, sinon fusion avec GPT."""
    local_conf = local.get("confidence", 0)
    ai_conf = ai.get("confidence", 0)

    if local_conf >= FUZZY_HIGH and local.get("normalized", "").lower() != original.lower():
        merged = {**ai, **local}
        merged["variants"] = list(
            dict.fromkeys(
                (local.get("variants") or [])
                + (ai.get("variants") or [])
                + [local["normalized"], original]
            )
        )[:10]
        merged["notes"] = f"local({local.get('local_source')}) + gpt"
        merged["ai_used"] = ai.get("ai_used", False)
        if local.get("arabic_name"):
            merged["arabic_name"] = local["arabic_name"]
        merged["confidence"] = max(local_conf, ai_conf)
        return merged

    if ai.get("ai_used"):
        merged = {**local, **ai}
        if not merged.get("arabic_name") and local.get("arabic_name"):
            merged["arabic_name"] = local["arabic_name"]
        merged["variants"] = list(
            dict.fromkeys((ai.get("variants") or []) + (local.get("variants") or []))
        )[:10]
        return merged

    return local


async def normalize_with_ai(
    name: str,
    language_hint: Optional[str] = None,
) -> Dict[str, Any]:
    from app.services.icl_selector import format_icl_block, select_icl_examples

    local_result = normalize_from_local_dictionary(name)

    client = get_openai_client()
    if client is None:
        local_result["notes"] = "OpenAI non configuré — dictionnaire local"
        return local_result

    icl_examples = select_icl_examples(name, limit=8)
    icl_block = format_icl_block(icl_examples)
    hint = f"Langue probable : {language_hint}." if language_hint else ""
    if icl_block:
        hint = f"{hint}\n\n{icl_block}".strip()

    model = settings.openai_model_complex if _is_complex_case(name) else settings.openai_model_correction
    user_prompt = (
        COMPLEX_CASE_PROMPT.format(name=name)
        if _is_complex_case(name)
        else USER_PROMPT_TEMPLATE.format(name=name, language_hint=hint)
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": build_system_prompt(icl_block=icl_block)},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        data = _parse_json_response(content)
        ai_result = {
            "normalized": title_case_name(data.get("normalized", name)),
            "arabic_name": data.get("arabic_name", ""),
            "confidence": int(data.get("confidence", 85)),
            "variants": data.get("variants", []),
            "language_detected": data.get("language_detected", "fr"),
            "notes": data.get("notes", ""),
            "ai_used": True,
            "model": model,
        }
        return _merge_local_and_ai(local_result, ai_result, name)

    except (RateLimitError, APIStatusError, APIConnectionError) as exc:
        logger.error("OpenAI normalization failed: %s", exc)
        local_result["notes"] = f"GPT indisponible ({_openai_error_message(exc)}) — dictionnaire local"
        return local_result
    except Exception as exc:
        logger.error("OpenAI normalization failed: %s", exc)
        local_result["notes"] = f"GPT erreur — dictionnaire local: {exc}"
        return local_result


def _openai_error_message(exc: Exception) -> str:
    if isinstance(exc, RateLimitError):
        return "quota ou facturation OpenAI inactive"
    if isinstance(exc, APIStatusError) and exc.status_code == 429:
        return "compte OpenAI inactif — vérifiez la facturation"
    return str(exc)[:120]


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """Transcription nom mauritanien uniquement (delegue au pipeline vocal)."""
    from app.services.voice_name import transcribe_mauritanian_name

    result = await transcribe_mauritanian_name(audio_bytes, filename)
    name = result.get("extracted_name") or result.get("transcription", "")
    if not name:
        raise ValueError("Whisper n'a pas reconnu de nom dans l'audio.")
    return name
