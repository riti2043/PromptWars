"""
clean.py: Input normalization, de-obfuscation, and obfuscation detection.
- Unicode NFKC normalization
- Stripping zero-width, bidi, and unprintable control characters
- Homoglyph folding (Cyrillic/Greek lookalikes to Latin)
- Recursive decoding (Base64, Hex, URL-encoded) up to depth 3
- Shannon entropy detection on long alphanumeric tokens
- RAW text is preserved; decoded text is scanned for threats but NEVER used as a source of values.
"""

import math
import re
import unicodedata
import urllib.parse
import base64
from typing import Dict, List, Tuple, Any

# Zero-width and invisible characters
ZERO_WIDTH_CHARS = {
    '\u200B', '\u200C', '\u200D', '\uFEFF', '\u200E', '\u200F',
    '\u202A', '\u202B', '\u202C', '\u202D', '\u202E', '\u00AD'
}

# Homoglyph lookup table: Cyrillic / Greek to standard Latin lowercase
HOMOGLYPH_MAP = {
    # Cyrillic small & capital
    'а': 'a', 'А': 'A', 'в': 'b', 'В': 'B', 'с': 'c', 'С': 'C',
    'е': 'e', 'Е': 'E', 'н': 'h', 'Н': 'H', 'і': 'i', 'І': 'I',
    'ј': 'j', 'Ј': 'J', 'к': 'k', 'К': 'K', 'м': 'm', 'М': 'M',
    'о': 'o', 'О': 'O', 'р': 'p', 'Р': 'P', 'ѕ': 's', 'Ѕ': 'S',
    'т': 't', 'Т': 'T', 'у': 'y', 'У': 'Y', 'х': 'x', 'Х': 'X',
    # Greek
    'α': 'a', 'Α': 'A', 'β': 'b', 'Β': 'B', 'γ': 'y', 'ε': 'e',
    'Ε': 'E', 'ι': 'i', 'Ι': 'I', 'κ': 'k', 'Κ': 'K', 'ν': 'v',
    'ο': 'o', 'Ο': 'O', 'ρ': 'p', 'Ρ': 'P', 'τ': 't', 'Τ': 'T',
    'χ': 'x', 'Χ': 'X'
}

def calculate_shannon_entropy(text: str) -> float:
    """Calculate Shannon entropy (bits per character) of a string."""
    if not text:
        return 0.0
    entropy = 0.0
    length = len(text)
    counts = {}
    for char in text:
        counts[char] = counts.get(char, 0) + 1
    for count in counts.values():
        prob = count / length
        entropy -= prob * math.log2(prob)
    return entropy

def detect_mixed_script(text: str) -> bool:
    """Detect if a single word token mixes Latin with Cyrillic or Greek characters."""
    tokens = re.findall(r'[^\s,;:?!.]+', text)
    for token in tokens:
        has_latin = bool(re.search(r'[a-zA-Z]', token))
        has_cyrillic = any('\u0400' <= ch <= '\u04FF' for ch in token)
        has_greek = any('\u0370' <= ch <= '\u03FF' for ch in token)
        if has_latin and (has_cyrillic or has_greek):
            return True
    return False

def fold_homoglyphs(text: str) -> Tuple[str, bool]:
    """Fold Cyrillic and Greek homoglyphs into Latin equivalents."""
    folded = []
    has_homoglyphs = False
    for ch in text:
        if ch in HOMOGLYPH_MAP:
            folded.append(HOMOGLYPH_MAP[ch])
            has_homoglyphs = True
        else:
            folded.append(ch)
    return "".join(folded), has_homoglyphs

def strip_invisible_chars(text: str) -> Tuple[str, bool]:
    """Strip zero-width, bidi, and unprintable control characters."""
    cleaned = []
    found_invisible = False
    for ch in text:
        if ch in ZERO_WIDTH_CHARS:
            found_invisible = True
            continue
        # Also strip non-printable controls except newline and tab
        category = unicodedata.category(ch)
        if category.startswith('C') and ch not in ('\n', '\r', '\t'):
            found_invisible = True
            continue
        cleaned.append(ch)
    return "".join(cleaned), found_invisible

def try_decode_nested(text: str, max_depth: int = 3) -> Tuple[List[str], bool]:
    """
    Attempt recursive decoding of base64, hex, and URL encoding.
    Returns list of newly uncovered plaintexts and whether a decoded payload was found.
    """
    decoded_payloads = []
    current = text
    found_decoded = False

    for _ in range(max_depth):
        changed = False

        # 1. URL decoding
        try:
            unquoted = urllib.parse.unquote(current)
            if unquoted != current and len(unquoted) > 3:
                decoded_payloads.append(unquoted)
                current = unquoted
                changed = True
                found_decoded = True
        except Exception:
            pass

        # 2. Hex decoding (matches strings of format 48656c6c6f or \x48\x65...)
        hex_candidates = re.findall(r'(?:(?:\\x)?[0-9a-fA-F]{2}){4,}', current)
        for cand in hex_candidates:
            clean_hex = cand.replace('\\x', '')
            if len(clean_hex) % 2 == 0 and len(clean_hex) >= 8:
                try:
                    raw_bytes = bytes.fromhex(clean_hex)
                    decoded_str = raw_bytes.decode('utf-8', errors='ignore')
                    if any(c.isalnum() for c in decoded_str) and len(decoded_str) >= 4:
                        decoded_payloads.append(decoded_str)
                        current = current.replace(cand, decoded_str)
                        changed = True
                        found_decoded = True
                except Exception:
                    pass

        # 3. Base64 decoding
        b64_candidates = re.findall(r'[A-Za-z0-9+/]{8,}={0,2}', current)
        for cand in b64_candidates:
            if len(cand) % 4 == 0:
                try:
                    raw_bytes = base64.b64decode(cand, validate=True)
                    decoded_str = raw_bytes.decode('utf-8', errors='ignore')
                    if len(decoded_str) >= 4 and any(c.isalnum() for c in decoded_str):
                        decoded_payloads.append(decoded_str)
                        current = current.replace(cand, decoded_str)
                        changed = True
                        found_decoded = True
                except Exception:
                    pass

        if not changed:
            break

    return decoded_payloads, found_decoded

def clean_input(raw_text: str) -> Dict[str, Any]:
    """
    Execute stage 1 pipeline:
    - Retains RAW text untouched for literal extraction.
    - Produces canonical text with NFKC, homoglyphs folded, and invisible characters stripped.
    - Flags all obfuscation signals: invisible chars, homoglyphs, mixed script, high entropy, decoded payloads.
    """
    raw = raw_text or ""
    # Unicode NFKC
    nfkc_text = unicodedata.normalize('NFKC', raw)

    # Strip invisible/zero-width chars
    no_invis, found_invisible = strip_invisible_chars(nfkc_text)

    # Detect mixed script before homoglyph folding
    found_mixed_script = detect_mixed_script(no_invis)

    # Homoglyph folding
    folded_text, found_homoglyphs = fold_homoglyphs(no_invis)

    # High entropy detection on tokens with length >= 12
    found_high_entropy = False
    tokens = re.findall(r'[A-Za-z0-9+/=]{12,}', raw)
    for tok in tokens:
        entropy = calculate_shannon_entropy(tok)
        if entropy > 4.2:  # High entropy indicates compressed/encrypted/base64 blob
            found_high_entropy = True
            break

    # Recursive decoding for scanning
    decoded_payloads, found_decoded = try_decode_nested(folded_text, max_depth=3)

    signals = []
    if found_invisible:
        signals.append("invisible_chars")
    if found_homoglyphs or found_mixed_script:
        signals.append("homoglyphs_or_mixed_script")
    if found_high_entropy:
        signals.append("high_entropy_blob")
    if found_decoded:
        signals.append("nested_encoded_payload")

    # Canonical text is trimmed and whitespace normalized
    canonical = re.sub(r'\s+', ' ', folded_text).strip()

    return {
        "raw_text": raw,
        "canonical_text": canonical,
        "decoded_scan_texts": decoded_payloads,
        "obfuscation_signals": signals,
        "has_obfuscation": len(signals) > 0
    }
