"""
schemas.py: Strict Pydantic v2 schemas for all requests, responses, and verdict payloads.
Fail-closed validation on every API endpoint.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict

class ScreenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command: str = Field(..., max_length=500, description="Untrusted natural-language user command")
    memo: Optional[str] = Field(None, max_length=60, description="Optional isolated memo field")

class ValueSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: Any
    span: List[int] = Field(..., min_length=2, max_length=2, description="[start, end] char offsets in raw text")

class VerifiedEntities(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Optional[ValueSpan] = None
    payee: Optional[ValueSpan] = None

class LayerTraceNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    layer: str
    result: Literal["PASS", "FLAG", "FAIL", "SKIPPED"]
    score: int
    note: str

class MandatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str
    intent: str
    amount: float
    currency: str
    payee_id: str
    payee_name: str
    memo: str
    issued_at: str

class SignedMandate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: MandatePayload
    payload_hash: str
    signature: str

class VerdictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str
    policy_version: str
    input_sha256: str
    verdict: Literal["APPROVED", "BLOCKED"]
    reason_code: str
    risk_score: int = Field(..., ge=0, le=100)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    threat_category: Literal[
        "NONE",
        "PROMPT_INJECTION",
        "JAILBREAK_ROLEPLAY",
        "POLICY_OVERRIDE",
        "MEMO_INJECTION",
        "OBFUSCATION",
        "DATA_EXFILTRATION",
        "AMBIGUOUS_REQUEST",
        "OUT_OF_SCOPE"
    ]
    owasp_ref: str
    explanation: str
    intent: Literal["BALANCE_INQUIRY", "TRANSFER", "OTHER"]
    verified: VerifiedEntities
    layer_trace: List[LayerTraceNode]
    degraded_mode: bool
    mandate: Optional[SignedMandate] = None
    confirmation_text: Optional[str] = None
    clarifying_question: Optional[str] = None

class ExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mandate: SignedMandate

class AccountResponse(BaseModel):
    account_id: str
    user_name: str
    currency: str
    balance: float
    session_spent: float
    session_transfers: int
    saved_payees: List[Dict[str, Any]]
    recent_transactions: List[Dict[str, Any]]
