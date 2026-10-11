"""
pipeline.py: The complete 5-layer Bankism Gateway execution pipeline.
1. clean: NFKC, invisible chars, homoglyph folding, decoding, entropy.
2. screen: memo split/sanitize, policy rule scan, strict grammar.
3. read: quarantined LLM call with nonce and canary, fail-closed offline fallback.
4. verify: Literal Provenance Engine (substring & offsets on RAW text) + policy checks.
5. mandate: HMAC-SHA256 signature generation and code-rendered confirmation on APPROVED.
"""

import hashlib
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from .clean import clean_input
from .screen import split_and_sanitize_memo, run_rule_engine, check_strict_grammar, POLICY
from .read import read_with_quarantine
from .verify import verify_provenance_and_policy
from .mandate import generate_mandate, render_code_confirmation
from .mock_bank import bank_instance
from .schemas import VerdictResponse, LayerTraceNode, VerifiedEntities, ValueSpan, SignedMandate, MandatePayload

async def execute_firewall_pipeline(
    command: str,
    memo: Optional[str] = None,
    llm_mode: str = "offline",
    model_name: str = "gemini-2.5-flash",
    simulate_compromise: bool = False
) -> Dict[str, Any]:
    """
    Main firewall pipeline coordinating the 5 layers. Returns validated dictionary matching VerdictResponse.
    """
    request_id = f"REQ_{uuid.uuid4().hex[:12].upper()}"
    input_sha256 = hashlib.sha256((command + (memo or "")).encode("utf-8")).hexdigest()
    layer_trace = []
    total_risk_score = 0
    threat_category = "NONE"
    owasp_ref = "None"
    reasons = []
    clarifying_question = None

    # ==========================================
    # LAYER 1: CLEAN
    # ==========================================
    clean_res = clean_input(command)
    raw_text = clean_res["raw_text"]
    canonical_text = clean_res["canonical_text"]
    obfuscation_signals = clean_res["obfuscation_signals"]
    decoded_scans = clean_res["decoded_scan_texts"]

    clean_layer_score = len(obfuscation_signals) * POLICY["weights"]["obfuscation_signal"]
    total_risk_score += clean_layer_score

    if obfuscation_signals:
        threat_category = "OBFUSCATION"
        owasp_ref = "ASI01"
        reasons.append(f"Obfuscation signals detected: {', '.join(obfuscation_signals)}")
        layer_trace.append(LayerTraceNode(
            layer="Clean",
            result="FLAG",
            score=clean_layer_score,
            note=f"Flagged {len(obfuscation_signals)} obfuscation anomaly(ies)"
        ))
    else:
        layer_trace.append(LayerTraceNode(
            layer="Clean",
            result="PASS",
            score=0,
            note="Normalized via NFKC, zero-width chars and homoglyphs clear"
        ))

    # ==========================================
    # LAYER 2: SCREEN
    # ==========================================
    memo_res = split_and_sanitize_memo(canonical_text, dedicated_memo=memo)
    command_for_eval = memo_res["command_text"]
    sanitized_memo = memo_res["sanitized_memo"]
    memo_injection = memo_res["memo_injection_detected"]
    stripped_memo = memo_res["stripped_due_to_whitelist"]

    rule_hits, rule_score = run_rule_engine(command_for_eval, decoded_scans)
    total_risk_score += rule_score

    if memo_injection:
        total_risk_score += POLICY["weights"]["memo_stripped_injection"]
        threat_category = "MEMO_INJECTION"
        owasp_ref = "ASI06"
        reasons.append("Memo field contains injected imperative verbs or override tokens")

    if rule_hits:
        for r in rule_hits:
            reasons.append(r["explanation"])
            threat_category = r["category"]
            owasp_ref = r["owasp"]

    grammar_res = check_strict_grammar(command_for_eval)

    screen_status = "PASS"
    screen_note = "Passed rule checks"
    if rule_hits or memo_injection:
        screen_status = "FAIL"
        screen_note = f"Triggered {len(rule_hits)} rule hit(s) / memo injection"
    elif stripped_memo:
        screen_status = "FLAG"
        screen_note = "Memo contained non-whitelisted characters that were stripped"

    layer_trace.append(LayerTraceNode(
        layer="Screen",
        result=screen_status,
        score=rule_score + (POLICY["weights"]["memo_stripped_injection"] if memo_injection else 0),
        note=screen_note
    ))

    # ==========================================
    # LAYER 3: READ (Quarantined LLM)
    # ==========================================
    read_res = await read_with_quarantine(
        canonical_text=command_for_eval,
        llm_mode=llm_mode,
        model_name=model_name,
        simulate_compromise=simulate_compromise
    )

    degraded_mode = read_res["degraded_mode"]
    llm_reading = read_res["reading"]

    if read_res["canary_leak"]:
        total_risk_score = 100
        threat_category = "DATA_EXFILTRATION"
        owasp_ref = "ASI02"
        reasons.append("Canary token leak identified in quarantined reader output")
        layer_trace.append(LayerTraceNode(
            layer="Read",
            result="FAIL",
            score=100,
            note="Canary exfiltration detected"
        ))
    elif read_res["nonce_breach"]:
        total_risk_score = 100
        threat_category = "PROMPT_INJECTION"
        owasp_ref = "ASI01"
        reasons.append("Boundary nonce manipulation detected in user payload")
        layer_trace.append(LayerTraceNode(
            layer="Read",
            result="FAIL",
            score=100,
            note="Boundary nonce forged"
        ))
    elif llm_reading and llm_reading.attack_flag:
        total_risk_score += POLICY["weights"]["llm_attack_flag"]
        threat_category = llm_reading.attack_category or "PROMPT_INJECTION"
        reasons.append("Quarantined LLM reader flagged potential adversarial intent")
        layer_trace.append(LayerTraceNode(
            layer="Read",
            result="FLAG",
            score=POLICY["weights"]["llm_attack_flag"],
            note=f"Flagged by LLM as {threat_category}"
        ))
    else:
        read_note = "Grammar-only mode (offline)" if degraded_mode else "LLM reader passed without attack flags"
        layer_trace.append(LayerTraceNode(
            layer="Read",
            result="PASS",
            score=0,
            note=read_note
        ))

    # Determine Intent
    intent = "OTHER"
    target_amount = None
    target_payee = None

    if grammar_res["matched"]:
        intent = grammar_res["intent"]
        if grammar_res["extracted_amount"]:
            try:
                raw_a = grammar_res["extracted_amount"].lower().replace('₹', '').replace('rs.', '').replace('rs', '').strip()
                if 'k' in raw_a:
                    target_amount = float(raw_a.replace('k', '')) * 1000
                elif 'lakh' in raw_a:
                    target_amount = float(raw_a.replace('lakh', '')) * 100000
                else:
                    target_amount = float(raw_a)
            except Exception:
                target_amount = None
        target_payee = grammar_res["extracted_payee"]
    elif llm_reading and not degraded_mode:
        intent = llm_reading.intent
        target_amount = llm_reading.amount
        target_payee = llm_reading.payee

    # ==========================================
    # LAYER 4: VERIFY (Literal Provenance & Policy)
    # ==========================================
    verified_entities = VerifiedEntities()
    signed_mandate = None
    confirmation_text = None

    if intent == "BALANCE_INQUIRY":
        verify_status = "PASS"
        verify_note = "Balance check requires no monetary provenance"
        layer_trace.append(LayerTraceNode(
            layer="Verify",
            result="PASS",
            score=0,
            note=verify_note
        ))
    elif intent == "TRANSFER":
        prov_res = verify_provenance_and_policy(
            raw_text=raw_text,
            extracted_amount=target_amount,
            extracted_payee_name=target_payee,
            mock_bank_state=bank_instance.get_account_summary(),
            policy_cfg=POLICY
        )

        if prov_res["verified_amount"]:
            verified_entities.amount = ValueSpan(
                value=prov_res["verified_amount"]["value"],
                span=prov_res["verified_amount"]["span"]
            )
        if prov_res["verified_payee"]:
            verified_entities.payee = ValueSpan(
                value=prov_res["verified_payee"]["canonical_name"],
                span=prov_res["verified_payee"]["span"]
            )

        if not prov_res["passed"]:
            total_risk_score += POLICY["weights"]["provenance_failure"]
            if prov_res["provenance_failures"]:
                reasons.extend(prov_res["provenance_failures"])
                if threat_category == "NONE":
                    threat_category = "AMBIGUOUS_REQUEST"
                    owasp_ref = "ASI01"
                if prov_res["candidate_amounts_count"] == 0:
                    clarifying_question = "What amount would you like to transfer?"
                elif prov_res["candidate_payees_count"] == 0:
                    clarifying_question = "Which saved payee (Alice, Bob, or Charlie) do you wish to transfer funds to?"

            if prov_res["policy_violations"]:
                reasons.extend(prov_res["policy_violations"])
                if threat_category == "NONE":
                    threat_category = "POLICY_OVERRIDE"

            layer_trace.append(LayerTraceNode(
                layer="Verify",
                result="FAIL",
                score=POLICY["weights"]["provenance_failure"],
                note=f"Failed literal provenance / policy ({len(prov_res['provenance_failures']) + len(prov_res['policy_violations'])} issues)"
            ))
        else:
            layer_trace.append(LayerTraceNode(
                layer="Verify",
                result="PASS",
                score=0,
                note=f"Proven literal amount (₹{verified_entities.amount.value}) and payee ({verified_entities.payee.value})"
            ))
    else:
        # OUT OF SCOPE / UNRECOGNIZED INTENT
        total_risk_score += 40
        if threat_category == "NONE":
            threat_category = "OUT_OF_SCOPE"
        reasons.append("Unrecognized intent or request outside of banking scope")
        layer_trace.append(LayerTraceNode(
            layer="Verify",
            result="FAIL",
            score=40,
            note="Unrecognized financial intent"
        ))

    # ==========================================
    # LAYER 5: SIGN (Mandate Generation)
    # ==========================================
    total_risk_score = min(100, max(0, total_risk_score))

    # Decision Logic: Fail Closed
    is_approved = (
        total_risk_score < POLICY["thresholds"]["approval_max_score"]
        and len(rule_hits) == 0
        and not memo_injection
        and len(obfuscation_signals) == 0
        and (intent == "BALANCE_INQUIRY" or (intent == "TRANSFER" and verified_entities.amount is not None and verified_entities.payee is not None))
    )

    if is_approved:
        verdict = "APPROVED"
        reason_code = "REQUEST_APPROVED"
        if intent == "TRANSFER":
            payee_match = next(p for p in bank_instance.saved_payees if p["name"] == verified_entities.payee.value)
            mandate_obj = generate_mandate(
                request_id=request_id,
                intent=intent,
                amount=float(verified_entities.amount.value),
                currency="INR",
                payee_id=payee_match["id"],
                payee_name=payee_match["name"],
                sanitized_memo=sanitized_memo,
                issued_at=datetime.utcnow().isoformat() + "Z"
            )
            signed_mandate = SignedMandate(
                payload=MandatePayload(**mandate_obj["payload"]),
                payload_hash=mandate_obj["payload_hash"],
                signature=mandate_obj["signature"]
            )
            confirmation_text = render_code_confirmation(mandate_obj)
            layer_trace.append(LayerTraceNode(
                layer="Sign",
                result="PASS",
                score=0,
                note="Mandate issued and HMAC-SHA256 signed"
            ))
        else:
            layer_trace.append(LayerTraceNode(
                layer="Sign",
                result="PASS",
                score=0,
                note="Balance inquiry approved (no financial mandate required)"
            ))
            confirmation_text = f"Your current account balance is ₹{bank_instance.balance:,.2f} INR."
    else:
        verdict = "BLOCKED"
        reason_code = f"BLOCKED_{threat_category}" if threat_category != "NONE" else "BLOCKED_HIGH_RISK"
        layer_trace.append(LayerTraceNode(
            layer="Sign",
            result="FAIL",
            score=0,
            note="Execution blocked; mandate withholding enforced"
        ))

    # Risk level classification
    if total_risk_score <= POLICY["thresholds"]["low_max"]:
        risk_level = "LOW"
    elif total_risk_score <= POLICY["thresholds"]["medium_max"]:
        risk_level = "MEDIUM"
    elif total_risk_score <= POLICY["thresholds"]["high_max"]:
        risk_level = "HIGH"
    else:
        risk_level = "CRITICAL"

    explanation = "; ".join(reasons) if reasons else "Request meets all deterministic security policies and literal provenance checks."

    response_dict = {
        "request_id": request_id,
        "policy_version": POLICY.get("policy_version", "1.0.0"),
        "input_sha256": input_sha256,
        "verdict": verdict,
        "reason_code": reason_code,
        "risk_score": total_risk_score,
        "risk_level": risk_level,
        "threat_category": threat_category,
        "owasp_ref": owasp_ref,
        "explanation": explanation,
        "intent": intent,
        "verified": verified_entities.model_dump(),
        "layer_trace": [node.model_dump() for node in layer_trace],
        "degraded_mode": degraded_mode,
        "mandate": signed_mandate.model_dump() if signed_mandate else None,
        "confirmation_text": confirmation_text,
        "clarifying_question": clarifying_question
    }

    # Validate output schema against Pydantic model
    return VerdictResponse(**response_dict).model_dump()
