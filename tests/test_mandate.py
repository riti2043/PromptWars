import pytest
from src.mandate import generate_mandate, verify_mandate_signature, render_code_confirmation
from src.mock_bank import bank_instance

def test_mandate_generation_and_tamper_detection():
    mandate = generate_mandate(
        request_id="REQ_TEST_101",
        intent="TRANSFER",
        amount=500.0,
        currency="INR",
        payee_id="PAYEE_01",
        payee_name="Alice Sharma",
        sanitized_memo="Lunch",
        issued_at="2026-10-11T10:00:00Z"
    )

    # Valid signature
    assert verify_mandate_signature(mandate["payload"], mandate["signature"]) is True

    # Tamper with amount
    tampered_payload = dict(mandate["payload"])
    tampered_payload["amount"] = 5000.0
    assert verify_mandate_signature(tampered_payload, mandate["signature"]) is False

def test_bank_execution_and_anti_replay():
    bank_instance.reset()
    mandate = generate_mandate(
        request_id="REQ_EXEC_202",
        intent="TRANSFER",
        amount=500.0,
        currency="INR",
        payee_id="PAYEE_01",
        payee_name="Alice Sharma",
        sanitized_memo="Lunch",
        issued_at="2026-10-11T10:00:00Z"
    )

    # First execution succeeds
    res1 = bank_instance.execute_mandate(mandate["payload"], mandate["signature"])
    assert res1["success"] is True
    assert bank_instance.balance == 49500.0

    # Second execution of same request_id fails with anti-replay
    res2 = bank_instance.execute_mandate(mandate["payload"], mandate["signature"])
    assert res2["success"] is False
    assert "REPLAY_DETECTED" in res2["error"]
