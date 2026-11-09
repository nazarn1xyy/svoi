"""Content filter and age-in-text detector: pure functions (BACKEND S11)."""

import re

from svoi_contracts.enums import ContentBlockReason

from svoi_api.domains.safety.stopwords import STOPWORDS

_HOMOGLYPHS = str.maketrans({"a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "x": "х", "i": "і"})
_LEET = str.maketrans({"0": "о", "3": "з", "4": "ч", "6": "б", "@": "а"})
# "т3мки": 3 also stands for Cyrillic ye
_LEET_ALT = str.maketrans({"0": "о", "3": "е", "4": "ч", "6": "б", "@": "а"})
_TLDS = ("com", "ua", "ru", "net", "org", "io", "me", "link", "xyz")
_LINK = re.compile(
    r"(https?://|www\.|t\s*\.\s*me|telegram\s*\.\s*me|"
    r"\b[a-z0-9-]{2,}\s*\.\s*(?:" + "|".join(_TLDS) + r")\b)",
    re.IGNORECASE,
)
_MENTION = re.compile(r"@\s*[a-zA-Z0-9_]{4,}")
_PHONE = re.compile(r"(?:\+?\d[\s\-()]*){9,}")
_SEP = re.compile(r"(?<=\w)[\s.\-_*]+(?=\w(?:[\s.\-_*]|$))")
_AGE_PATTERNS = (
    re.compile(r"\b(?:мені|мне)\s+(\d{1,2})\b"),
    re.compile(r"\b(\d{1,2})\s*(?:років|рокiв|роки|рік|лет|год|года|yo|y\.o\.)\b"),
    re.compile(r"\((\d{1,2})\)"),
    re.compile(r"\b(\d{1,2})\s*!"),
)
_SCHOOL = re.compile(
    r"\b(?:в|у)\s*(?:9|10|11)\s*(?:класі|классе|клас|класс)\b|школяр|школярка|школьник|школьница"
)
SCHOOL_AGE = 15
_MIN_PLAUSIBLE, _MAX_PLAUSIBLE = 10, 99


def _squash_repeats(text: str) -> str:
    return re.sub(r"(.)\1+", r"\1", text)


def normalize(text: str, leet: dict[int, str] = _LEET) -> str:
    """Lowercase, Latin/Cyrillic homoglyphs, leet, repeated letters, separators inside words."""
    out = text.lower().translate(leet).translate(_HOMOGLYPHS)
    out = _SEP.sub("", out)
    return _squash_repeats(out)


_NORMAL_STOPWORDS = tuple({normalize(w) for w in STOPWORDS})


def _stopword(text: str) -> bool:
    for flat in {normalize(text), normalize(text, _LEET_ALT)}:
        joined = flat.replace(" ", "")
        if any(w in flat or w.replace(" ", "") in joined for w in _NORMAL_STOPWORDS):
            return True
    return False


def check_text(text: str) -> ContentBlockReason | None:
    """First reason the text is blocked: link, mention, phone, stopword; None if clean."""
    if _LINK.search(text) or _LINK.search(re.sub(r"\s+", "", text)):
        return ContentBlockReason.link
    if _MENTION.search(text):
        return ContentBlockReason.mention
    if _PHONE.search(text):
        return ContentBlockReason.phone
    if _stopword(text):
        return ContentBlockReason.stopword
    return None


def detect_age_mention(text: str) -> int | None:
    """Age the text claims ("мені 17", "17 років", "в 10 класі"), or None."""
    low = text.lower()
    for pattern in _AGE_PATTERNS:
        for match in pattern.finditer(low):
            age = int(match.group(1))
            if _MIN_PLAUSIBLE <= age <= _MAX_PLAUSIBLE:
                return age
    if _SCHOOL.search(low):
        return SCHOOL_AGE
    return None
