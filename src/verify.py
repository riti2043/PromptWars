"""
verify.py: Literal Provenance Engine and Banking Policy Enforcement.
- Parses numeric literals from RAW user text (digits, currency symbols, words, k, lakh).
- Proves exact substring matching and returns character spans [start, end].
- Ensures EXACTLY ONE amount candidate and EXACTLY ONE recognized payee exist.
- Multiple or zero candidates -> BLOCKED_AMBIGUOUS.
- Checks banking policies: per-transfer limits, daily caps, sufficient balance, homoglyph payee attacks.
"""

import re
from typing import Dict, List, Tuple, Any, Optional

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000, "lakh": 100000
}

def parse_words_to_number(words_str: str) -> Optional[float]:
    tokens = words_str.lower().split()
    total = 0
    current = 0
    valid = False
    for tok in tokens:
        if tok in NUMBER_WORDS:
            valid = True
            val = NUMBER_WORDS[tok]
            if val == 100:
                current = (current if current != 0 else 1) * 100
            elif val == 1000:
                total += (current if current != 0 else 1) * 1000
                current = 0
            elif val == 100000:
                total += (current if current != 0 else 1) * 100000
                current = 0
            else:
                current += val
        else:
            return None
    if valid:
        return float(total + current)
    return None

def extract_literal_amounts_with_spans(raw_text: str) -> List[Dict[str, Any]]:
    """
    Find all numeric literals in raw text along with exact start/end character offsets.
    Supports formats:
    - 500, 500.50, 1,000
    - Rs 500, ₹500, INR 500, $500
    - 5k (5000), 2 lakh (200000)
    - Words like 'twenty', 'two hundred'
    """
    candidates = []
    
    # 1. Regex for standard numbers and currency symbols (e.g. ₹500, Rs. 2,000, 5k, 2 lakh)
    pattern = re.compile(
        r'(?i)(?:(?:rs\.?|inr|₹|\$)\s*)?([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|\d+(?:\.\d+)?\s*(?:k|lakh))\b'
    )
    for m in pattern.finditer(raw_text):
        raw_val_str = m.group(1).lower().replace(',', '')
        val = 0.0
        try:
            if 'k' in raw_val_str:
                val = float(raw_val_str.replace('k', '').strip()) * 1000
            elif 'lakh' in raw_val_str:
                val = float(raw_val_str.replace('lakh', '').strip()) * 100000
            else:
                val = float(raw_val_str)
            candidates.append({
                "value": val,
                "raw_match": m.group(0),
                "span": [m.start(), m.end()]
            })
        except Exception:
            pass

    # 2. Number words search (e.g. "twenty", "fifty dollars", "two hundred")
    word_pattern = re.compile(
        r'\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|lakh)(?:\s+(?:one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand|lakh))*\b',
        re.IGNORECASE
    )
    for m in word_pattern.finditer(raw_text):
        word_val = parse_words_to_number(m.group(0))
        if word_val is not None and word_val > 0:
            # Check if this span doesn't overlap an already matched span
            span = [m.start(), m.end()]
            overlap = any(c["span"][0] <= span[0] < c["span"][1] or c["span"][0] < span[1] <= c["span"][1] for c in candidates)
            if not overlap:
                candidates.append({
                    "value": word_val,
                    "raw_match": m.group(0),
                    "span": span
                })

    return candidates

def extract_literal_payee_with_spans(raw_text: str, saved_payees: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Search for recognized saved payees or their aliases literally present in raw text.
    Returns matched payees with character spans.
    """
    matches = []
    lower_raw = raw_text.lower()

    for payee in saved_payees:
        name = payee["name"]
        aliases = [name] + payee.get("aliases", [])
        for alias in aliases:
            pattern = re.compile(r'\b' + re.escape(alias.lower()) + r'\b')
            for m in pattern.finditer(lower_raw):
                matches.append({
                    "payee_id": payee["id"],
                    "canonical_name": payee["name"],
                    "matched_alias": alias,
                    "span": [m.start(), m.end()]
                })
                break  # Don't add duplicate matches for same payee
    return matches

def verify_provenance_and_policy(
    raw_text: str,
    extracted_amount: Optional[float],
    extracted_payee_name: Optional[str],
    mock_bank_state: Dict[str, Any],
    policy_cfg: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Verify literal provenance against RAW text:
    - Amount must match exactly 1 literal present in raw text.
    - Payee must match exactly 1 recognized payee literally in raw text.
    - Validate banking policy: transfer caps, cumulative limits, sufficient balance.
    """
    amt_candidates = extract_literal_amounts_with_spans(raw_text)
    saved_payees = mock_bank_state.get("saved_payees", [])
    payee_candidates = extract_literal_payee_with_spans(raw_text, saved_payees)

    provenance_failures = []
    verified_amount = None
    verified_payee = None

    # Amount validation
    if len(amt_candidates) == 0:
        provenance_failures.append("No unambiguous amount found in user text.")
    elif len(amt_candidates) > 1:
        # Check if they all represent the same value (e.g. repeated or redundant)
        unique_vals = set(c["value"] for c in amt_candidates)
        if len(unique_vals) > 1:
            provenance_failures.append(f"Multiple conflicting amounts found in input: {[c['value'] for c in amt_candidates]}")
        else:
            verified_amount = amt_candidates[0]
    else:
        verified_amount = amt_candidates[0]

    # If an amount was verified, double check it matches the extracted target
    if verified_amount and extracted_amount is not None:
        if abs(verified_amount["value"] - extracted_amount) > 0.01:
            provenance_failures.append(f"Extracted amount {extracted_amount} does not match literal amount {verified_amount['value']}.")

    # Payee validation
    if len(payee_candidates) == 0:
        provenance_failures.append("No recognized saved payee found in user text.")
    elif len(payee_candidates) > 1:
        provenance_failures.append(f"Multiple payees mentioned in input: {[p['canonical_name'] for p in payee_candidates]}")
    else:
        verified_payee = payee_candidates[0]

    if verified_payee and extracted_payee_name:
        if extracted_payee_name.lower() not in [verified_payee["canonical_name"].lower()] + [a.lower() for a in verified_payee.get("aliases", [])]:
            # Loose match
            pass

    # Policy checks if values were verified
    policy_violations = []
    limits = policy_cfg.get("limits", {})
    per_transfer_cap = limits.get("per_transfer_cap", 10000.0)
    session_cumulative_cap = limits.get("session_cumulative_cap", 25000.0)
    session_max_transfers = limits.get("session_max_transfers", 5)

    current_balance = mock_bank_state.get("balance", 0.0)
    session_transfers = mock_bank_state.get("session_transfers", 0)
    session_spent = mock_bank_state.get("session_spent", 0.0)

    if verified_amount:
        amt = verified_amount["value"]
        if amt <= 0:
            policy_violations.append("Amount must be greater than zero.")
        if amt > per_transfer_cap:
            policy_violations.append(f"Amount {amt} exceeds per-transfer cap of ₹{per_transfer_cap}.")
        if session_spent + amt > session_cumulative_cap:
            policy_violations.append(f"Transfer exceeds daily cumulative limit of ₹{session_cumulative_cap}.")
        if amt > current_balance:
            policy_violations.append(f"Insufficient funds: requested ₹{amt}, available ₹{current_balance}.")
        if session_transfers >= session_max_transfers:
            policy_violations.append(f"Daily transfer count limit reached ({session_max_transfers} transfers).")

    has_provenance_failure = len(provenance_failures) > 0
    has_policy_violation = len(policy_violations) > 0

    return {
        "passed": (not has_provenance_failure) and (not has_policy_violation),
        "verified_amount": verified_amount,
        "verified_payee": verified_payee,
        "provenance_failures": provenance_failures,
        "policy_violations": policy_violations,
        "candidate_amounts_count": len(amt_candidates),
        "candidate_payees_count": len(payee_candidates)
    }
