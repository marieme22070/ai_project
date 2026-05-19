"""Arabic text utilities for display and normalization."""

import re

try:
    import arabic_reshaper
    from bidi.algorithm import get_display

    HAS_BIDI = True
except ImportError:
    HAS_BIDI = False


def reshape_arabic(text: str) -> str:
    if not text or not HAS_BIDI:
        return text
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def is_arabic(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text))
