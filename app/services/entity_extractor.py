"""Extraction d'entités (noms) depuis texte long ou documents administratifs."""

import re
from typing import List, Tuple

from app.utils.arabic import is_arabic

# Colonnes typiques des fichiers administratifs
NAME_COLUMN_HINTS = {
    "nom",
    "name",
    "prenom",
    "prénom",
    "firstname",
    "lastname",
    "nom_complet",
    "full_name",
    "citizen",
    "citoyen",
    "الاسم",
    "اسم",
}

# Mots à ignorer (en-têtes, labels)
SKIP_TOKENS = {
    "nom",
    "name",
    "prenom",
    "prénom",
    "id",
    "nni",
    "cin",
    "date",
    "naissance",
    "total",
    "nombre",
    "count",
}


def _looks_like_name(text: str) -> bool:
    t = text.strip()
    if len(t) < 2 or len(t) > 120:
        return False
    lower = t.lower()
    if lower in SKIP_TOKENS:
        return False
    if re.match(r"^[\d\s\-./:]+$", t):
        return False
    if re.match(r"^\d{4,}", t):
        return False
    # Au moins une lettre (latin ou arabe)
    if not re.search(r"[\w\u0600-\u06FF]", t):
        return False
    word_count = len(t.split())
    if word_count > 8:
        return False
    return True


def extract_names_from_text(text: str, max_names: int = 500) -> List[Tuple[str, int]]:
    """
    Extrait des noms probables d'un texte long.
    Retourne [(nom, ligne_approx), ...].
    """
    if not text or not text.strip():
        return []

    seen = set()
    results: List[Tuple[str, int]] = []

    lines = text.splitlines()
    for line_no, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue

        # CSV / TSV : prendre les colonnes ressemblant à des noms
        if "," in line or ";" in line or "\t" in line:
            sep = "\t" if "\t" in line else (";" if ";" in line else ",")
            parts = [p.strip().strip('"') for p in line.split(sep)]
            for part in parts:
                if _looks_like_name(part):
                    key = part.lower()
                    if key not in seen:
                        seen.add(key)
                        results.append((part, line_no))
        else:
            # Ligne entière ou segments séparés par |
            for segment in re.split(r"\s*\|\s*|\s{2,}", line):
                segment = segment.strip()
                if _looks_like_name(segment):
                    key = segment.lower()
                    if key not in seen:
                        seen.add(key)
                        results.append((segment, line_no))

        if len(results) >= max_names:
            break

    return results[:max_names]


def detect_name_columns(headers: List[str]) -> List[int]:
    """Indices des colonnes susceptibles de contenir des noms."""
    indices = []
    for i, h in enumerate(headers):
        h_clean = re.sub(r"[^\w\u0600-\u06FF]", "", h.lower())
        if any(hint in h_clean for hint in NAME_COLUMN_HINTS):
            indices.append(i)
        elif h_clean and _looks_like_name(h):
            indices.append(i)
    return indices if indices else list(range(min(3, len(headers))))


def linguistic_hint(name: str) -> str:
    """Tag linguistique rapide sans appel API."""
    if is_arabic(name):
        return "ar"
    lower = name.lower()
    if any(x in lower for x in ("ould", "oul", "wal", "mohamed", "mouhamed")):
        return "hassaniya"
    if any(x in lower for x in ("diallo", "sall", "ndiaye", "coulibaly", "traore")):
        return "pulaar|wolof|mixed"
    return "fr"
