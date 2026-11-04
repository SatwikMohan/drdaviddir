"""Offline query language identification shared by answers and speech."""

import re
from functools import lru_cache



SCRIPT_LANGUAGES = (
    ("\u0980", "\u09ff", "bn"), ("\u0a00", "\u0a7f", "pa"),
    ("\u0a80", "\u0aff", "gu"), ("\u0b00", "\u0b7f", "or"),
    ("\u0b80", "\u0bff", "ta"), ("\u0c00", "\u0c7f", "te"),
    ("\u0c80", "\u0cff", "kn"), ("\u0d00", "\u0d7f", "ml"),
    ("\u0600", "\u06ff", "ar"), ("\u0400", "\u04ff", "ru"),
    ("\u0370", "\u03ff", "el"), ("\u3040", "\u30ff", "ja"),
    ("\uac00", "\ud7af", "ko"), ("\u4e00", "\u9fff", "zh"),
)
ROMAN_HINDI = {
    "aap", "hai", "hain", "kya", "kaise", "kaisa", "kaisi", "mujhe",
    "batao", "bataye", "bataiye", "kripya", "dhanyavad", "shukriya",
    "namaste", "nahi", "mera", "meri", "hoga", "karo", "samjhao",
    "chahiye", "mein", "se", "ka", "ki", "ke", "yaar", "kal",
    "kariye", "kijiye", "dijiye", "batayein", "samjhayen",
    "jaana", "jana", "karna", "aaj", "aur", "ko", "yaad", "dilao",
    "yeh", "ye", "woh", "voh", "iska", "iski", "iske", "isme",
    "unhe", "unko", "agar", "lekin", "isliye", "kyunki", "liye",
    "sawaal", "jawab", "sahi", "galat", "zaroori", "zaruri",
    "hota", "hoti", "hote", "hogi", "honge", "karta", "karti",
    "rakha", "rakhi", "rakhe", "gaya", "gayi", "gaye", "diya",
    "dikhata", "dikhati", "batata", "batati", "samajh", "sakte",
    "kare", "karen", "karein", "jankari", "jaankari", "matlab",
    "samjhaiye", "samjhaye", "bataein", "bataen", "isko", "baare",
}
ROMAN_HINDI_STRONG = ROMAN_HINDI - {"ka", "ki", "ke", "se", "ko", "mein", "aur", "kal"}
ENGLISH_CLUES = {"the", "and", "is", "are", "what", "which", "with", "from", "this", "that", "their", "into", "before", "after"}
SHORT_LANGUAGE_WORDS = {
    "hola": "es", "gracias": "es", "bonjour": "fr", "merci": "fr",
    "ciao": "it", "hallo": "de", "namaste": "hinglish",
    "shukriya": "hinglish", "dhanyavad": "hinglish",
}
LATIN_CLUES = {
    "es": {"la", "del", "los", "explique", "estructura", "catálogo", "catalogo", "cuál", "cómo", "quiero", "dame", "años"},
    "pt": {"qual", "estrutura", "catálogo", "catalogo", "quais", "pode", "diga", "tabela"},
    "fr": {"quelle", "quelles", "catalogue", "expliquez", "donnez", "sont", "avec"},
    "de": {"wie", "struktur", "katalogs", "welche", "bitte", "sind"},
    "it": {"struttura", "spiega", "quale", "sono", "tabella"},
}


@lru_cache(maxsize=1)
def _classifier():
    try:
        from langid.langid import LanguageIdentifier, model
    except ImportError:
        return None
    return LanguageIdentifier.from_modelstring(model, norm_probs=True)


def detect_language(text: str, fallback: str = "en") -> str:
    """Use the query, with conservative fallback for short technical questions."""
    text = text.strip()
    if not text:
        return fallback
    if re.search(r"[\u0900-\u097f]", text):
        return "hi"
    for start, end, code in SCRIPT_LANGUAGES:
        if any(start <= char <= end for char in text):
            return code
    words = re.findall(r"[a-zA-ZÀ-ÿ]+", text.lower())
    if len(words) == 1 and words[0] in SHORT_LANGUAGE_WORDS:
        return SHORT_LANGUAGE_WORDS[words[0]]
    hindi_words = sum(word in ROMAN_HINDI for word in words)
    english_clues = len(set(words) & ENGLISH_CLUES)
    if (hindi_words >= 2 or (hindi_words and len(words) <= 2)
            or (len(words) <= 6 and english_clues < 2
                and any(word in ROMAN_HINDI_STRONG for word in words))):
        return "hinglish"
    # Abbreviations and identifiers dominate very short questions. Avoid a
    # language guess based on one product name or schema identifier.
    if len(words) < 4:
        return fallback
    if english_clues >= 3:
        return "en"
    clue_scores = {code: len(set(words) & clues) for code, clues in LATIN_CLUES.items()}
    best = max(clue_scores, key=clue_scores.get)
    if clue_scores[best] >= 2 and sum(score == clue_scores[best] for score in clue_scores.values()) == 1:
        return best
    # langid is unreliable on short code-mixed questions and identifiers: for
    # example, it calls "dgms ko elaborate kare" Spanish. Only the script and
    # distinctive word clues above can change the automatic reply language.
    return fallback
