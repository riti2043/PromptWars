"""
screen.py: Memo splitting & sanitization, YAML-driven policy rule scanning, and strict grammar check.
- Memo is strictly isolated from LLM prompts.
- Whitelist [A-Za-z0-9 .,'_-], max 60 chars.
- Memo raises MEMO_INJECTION if dangerous instruction patterns or transfer imperatives are found.
- Rule engine matches compiled regexes from policy.yaml.
- Safe banking checks: words like 'cancel', 'force', 'execute' do not trigger blocks on their own.
- Strict grammar check for balance inquiry and single transfer.
"""

import re
import yaml
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

POLICY_PATH = Path(__file__).resolve().parent.parent / "config" / "policy.yaml"

def load_policy() -> Dict[str, Any]:
    with open(POLICY_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

POLICY = load_policy()

# Markers that indicate an inline memo in the command text
INLINE_MEMO_PATTERNS = [
    r'(?i)\b(?:memo|note|ref|reference)\s*:\s*(.+)$',
    r'(?i)\b(?:for)\s+([a-zA-Z0-9\s.,\'_-]{2,60})$'
]

# Transfer verbs and imperative actions that should NOT be allowed inside a memo
MEMO_FORBIDDEN_PATTERNS = [
    r'(?i)\b(?:send|transfer|pay|wire)\b\s*(?:rs\.?|inr|₹|\$)?\s*\d+',
    r'(?i)\b(?:to|for)\s+[a-zA-Z0-9_]+\s*(?:account|acct|iban|upi)',
    r'(?i)(?:system:|assistant:|\[inst\]|<\|im_start\|>)',
    r'(?i)\b(?:cancel\s+that|disregard|ignore|instead|override|pay\s+[a-zA-Z]+)\b'
]

MEMO_ALLOWED_CHAR_REGEX = re.compile(r"^[A-Za-z0-9 .,'_-]*$")

def split_and_sanitize_memo(command: str, dedicated_memo: Optional[str] = None) -> Dict[str, Any]:
    """
    Split memo from command text if present, sanitize against character whitelist and max 60 chars.
    Ensures memo NEVER contains transfer verbs, role tags, or override instructions.
    """
    extracted_memo = (dedicated_memo or "").strip()
    command_text = command.strip()

    # If no dedicated memo was provided, check for inline memo markers
    if not extracted_memo:
        for pattern in INLINE_MEMO_PATTERNS:
            match = re.search(pattern, command_text)
            if match:
                extracted_memo = match.group(1).strip()
                # Remove the inline memo span from command text to avoid prompt confusion
                command_text = command_text[:match.start()].strip()
                break

    # Truncate / analyze length
    raw_memo = extracted_memo
    stripped_due_to_whitelist = False
    
    # Check for active injection patterns inside memo
    memo_injection_detected = False
    injection_reason = ""

    if raw_memo:
        for pat in MEMO_FORBIDDEN_PATTERNS:
            if re.search(pat, raw_memo):
                memo_injection_detected = True
                injection_reason = f"Memo contains command verbs or override tokens ({pat})"
                break

        # Whitelist filtering
        sanitized_chars = []
        for ch in raw_memo:
            if ch.isalnum() or ch in " .,'_-":
                sanitized_chars.append(ch)
            else:
                stripped_due_to_whitelist = True
        
        sanitized_memo = "".join(sanitized_chars)[:60].strip()
    else:
        sanitized_memo = ""

    return {
        "command_text": command_text,
        "raw_memo": raw_memo,
        "sanitized_memo": sanitized_memo,
        "stripped_due_to_whitelist": stripped_due_to_whitelist,
        "memo_injection_detected": memo_injection_detected,
        "injection_reason": injection_reason
    }

def run_rule_engine(text_to_scan: str, decoded_texts: List[str]) -> Tuple[List[Dict[str, Any]], int]:
    """
    Evaluate compiled policy regexes against canonical text and any decoded scan texts.
    Returns matched rules and cumulative rule penalty score.
    """
    hits = []
    total_rule_score = 0
    all_texts = [text_to_scan] + decoded_texts

    for rule in POLICY.get("rules", []):
        rule_regex = rule["regex"]
        for sample in all_texts:
            if re.search(rule_regex, sample):
                hits.append({
                    "id": rule["id"],
                    "category": rule["category"],
                    "weight": rule["weight"],
                    "owasp": rule.get("owasp", "ASI01"),
                    "explanation": rule["explanation"]
                })
                total_rule_score += rule["weight"]
                break

    return hits, total_rule_score

# Strict grammar matching for basic banking operations
BALANCE_GRAMMAR = re.compile(
    r'(?i)^(?:please\s+|can\s+you\s+|kindly\s+)?(?:check|show|what\s+is|view|get|tell\s+me)\s+(?:my\s+)?(?:account\s+)?balance(?:\s+please|\s+karo)?(?:\s*\?)?$'
)

BALANCE_GRAMMAR_ALT = re.compile(
    r'(?i)^(?:account\s+)?balance\s+check\s+karo$'
)

TRANSFER_GRAMMAR = re.compile(
    r'(?i)^(?:please\s+|can\s+you\s+|kindly\s+)?(?:send|transfer|pay)\s+(?:rs\.?|inr|₹|\$)?\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+k|[0-9]+\s+lakh|[a-z\s]+?)\s+(?:dollars\s+)?(?:to|for)\s+([a-zA-Z0-9_\s]+?)(?:\s+karo|\s+please)?$'
)

def check_strict_grammar(command_text: str) -> Dict[str, Any]:
    """
    Determine if input matches rigid banking grammar for BALANCE_INQUIRY or TRANSFER.
    Allows light polite prefixes and Hinglish fillers ('karo', 'please').
    """
    cleaned = command_text.strip()
    
    # Check Balance
    if BALANCE_GRAMMAR.match(cleaned) or BALANCE_GRAMMAR_ALT.match(cleaned):
        return {
            "matched": True,
            "intent": "BALANCE_INQUIRY",
            "extracted_amount": None,
            "extracted_payee": None
        }

    # Check Transfer
    match = TRANSFER_GRAMMAR.match(cleaned)
    if match:
        raw_amt = match.group(1).strip()
        raw_payee = match.group(2).strip()
        return {
            "matched": True,
            "intent": "TRANSFER",
            "extracted_amount": raw_amt,
            "extracted_payee": raw_payee
        }

    return {
        "matched": False,
        "intent": "OTHER",
        "extracted_amount": None,
        "extracted_payee": None
    }
