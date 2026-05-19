import re
import unicodedata

from unidecode import unidecode


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text.strip())


def title_case_name(name: str) -> str:
    parts = []
    for word in name.split():
        if word.upper() == word and len(word) > 1:
            parts.append(word.title())
        elif "'" in word or word.startswith("N'"):
            parts.append(word.upper() if word.startswith("N'") else word.title())
        else:
            parts.append(word.capitalize() if word.islower() else word.title())
    return " ".join(parts)


def strip_diacritics(text: str) -> str:
    return unidecode(normalize_unicode(text))


def clean_name_for_matching(name: str) -> str:
    text = strip_diacritics(name).lower()
    text = re.sub(r"[^\w\s'-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
