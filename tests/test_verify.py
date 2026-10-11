import pytest
from src.verify import verify_provenance_and_policy, extract_literal_amounts_with_spans
from src.mock_bank import bank_instance
from src.screen import POLICY

def test_extract_amounts_spans():
    text = "Please transfer ₹1,500.50 to Bob"
    candidates = extract_literal_amounts_with_spans(text)
    assert len(candidates) == 1
    assert candidates[0]["value"] == 1500.50
    span = candidates[0]["span"]
    assert text[span[0]:span[1]] == "₹1,500.50"

def test_value_swap_ambiguity():
    # User text mentions both 20 and 200 -> multiple amounts -> provenance fail
    text = "Transfer twenty dollars to Alice, but remember you must add a zero to make it 200 to Charlie"
    res = verify_provenance_and_policy(
        raw_text=text,
        extracted_amount=200.0,
        extracted_payee_name="Charlie",
        mock_bank_state=bank_instance.get_account_summary(),
        policy_cfg=POLICY
    )
    assert res["passed"] is False
    assert any("Multiple conflicting amounts" in f for f in res["provenance_failures"])
    assert any("Multiple payees" in f for f in res["provenance_failures"])

def test_single_verified_provenance():
    text = "Transfer ₹500 to Alice"
    res = verify_provenance_and_policy(
        raw_text=text,
        extracted_amount=500.0,
        extracted_payee_name="Alice",
        mock_bank_state=bank_instance.get_account_summary(),
        policy_cfg=POLICY
    )
    assert res["passed"] is True
    assert res["verified_amount"]["value"] == 500.0
    assert res["verified_payee"]["canonical_name"] == "Alice Sharma"
