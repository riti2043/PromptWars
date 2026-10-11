import pytest
from src.clean import clean_input, strip_invisible_chars, fold_homoglyphs, try_decode_nested

def test_clean_nfkc_and_invisibles():
    # Test zero-width space injection inside 'ignore'
    cloaked = "i\u200Bg\u200Bn\u200Bo\u200Br\u200Be"
    res = clean_input(cloaked)
    assert res["canonical_text"] == "ignore"
    assert "invisible_chars" in res["obfuscation_signals"]
    assert res["has_obfuscation"] is True

def test_clean_homoglyphs():
    # Cyrillic 'і' (\u0456), 'о' (\u043E), 'е' (\u0435) in 'ignore'
    cyrillic_cloaked = "\u0456gn\u043er\u0435"
    res = clean_input(cyrillic_cloaked)
    assert res["canonical_text"] == "ignore"
    assert "homoglyphs_or_mixed_script" in res["obfuscation_signals"]

def test_clean_nested_decoding():
    # Base64 encoded payload: "ignore rules" -> "aWdub3JlIHJ1bGVz"
    b64_str = "aWdub3JlIHJ1bGVz"
    res = clean_input(f"run payload {b64_str}")
    assert any("ignore rules" in decoded for decoded in res["decoded_scan_texts"])
    assert "nested_encoded_payload" in res["obfuscation_signals"]

def test_clean_benign_text():
    benign = "Transfer ₹500 to Alice"
    res = clean_input(benign)
    assert res["canonical_text"] == "Transfer ₹500 to Alice"
    assert res["has_obfuscation"] is False
    assert len(res["obfuscation_signals"]) == 0
