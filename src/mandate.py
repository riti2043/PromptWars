"""
mandate.py: Mandate generation, HMAC-SHA256 signing, and deterministic confirmation formatting.
- Mandates are constructed ONLY when a request is APPROVED.
- Canonical JSON is signed with MANDATE_SECRET.
- Confirmation text is rendered by CODE from the mandate, never by an LLM.
"""

import hmac
import hashlib
import json
import os
from typing import Dict, Any, Tuple

MANDATE_SECRET = os.getenv("MANDATE_SECRET", "bankism_hmac_secret_key_demo_change_in_prod_99").encode("utf-8")

def canonical_json_bytes(payload: Dict[str, Any]) -> bytes:
    """Format dictionary into deterministic, sorted canonical JSON bytes."""
    return json.dumps(payload, sort_keys=True, separators=(',', ':')).encode("utf-8")

def generate_mandate(
    request_id: str,
    intent: str,
    amount: float,
    currency: str,
    payee_id: str,
    payee_name: str,
    sanitized_memo: str,
    issued_at: str
) -> Dict[str, Any]:
    """
    Construct immutable transaction mandate payload and calculate HMAC-SHA256 signature.
    """
    payload = {
        "request_id": request_id,
        "intent": intent,
        "amount": round(amount, 2),
        "currency": currency,
        "payee_id": payee_id,
        "payee_name": payee_name,
        "memo": sanitized_memo,
        "issued_at": issued_at
    }

    canonical_bytes = canonical_json_bytes(payload)
    payload_hash = hashlib.sha256(canonical_bytes).hexdigest()
    signature = hmac.new(MANDATE_SECRET, canonical_bytes, hashlib.sha256).hexdigest()

    return {
        "payload": payload,
        "payload_hash": payload_hash,
        "signature": signature
    }

def verify_mandate_signature(payload: Dict[str, Any], signature: str) -> bool:
    """Recompute HMAC signature over canonical payload and verify tamper resistance."""
    try:
        canonical_bytes = canonical_json_bytes(payload)
        expected_sig = hmac.new(MANDATE_SECRET, canonical_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, signature)
    except Exception:
        return False

def render_code_confirmation(mandate: Dict[str, Any]) -> str:
    """
    Deterministic confirmation text rendered strictly by code.
    No model output is permitted to generate or alter this text.
    """
    p = mandate.get("payload", {})
    amt = p.get("amount", 0.0)
    curr = p.get("currency", "INR")
    payee = p.get("payee_name", "Unknown")
    memo = p.get("memo", "")
    req_id = p.get("request_id", "")

    curr_sym = "₹" if curr == "INR" else f"{curr} "
    memo_clause = f" with memo '{memo}'" if memo else ""

    return f"Please confirm authorization to transfer {curr_sym}{amt:,.2f} to {payee}{memo_clause}. [Mandate {req_id[:8]}]"
