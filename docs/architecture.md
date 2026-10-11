# Bankism: Architecture & System Design

**Target System:** Bankism Deterministic AI Firewall & Mandate Gateway  
**Date:** 11 October 2026  
**Security Boundary:** Untrusted Natural Language $\rightarrow$ Bankism Gateway $\rightarrow$ Mock Core Banking API  

---

## 1. System Philosophy: The Tripartite Principle

Bankism is constructed on an uncompromising core principle:
$$\text{The LLM Drafts} \longrightarrow \text{Code Proves} \longrightarrow \text{The User Signs}$$

1. **The LLM has zero execution authority:** The model is not equipped with function-calling tools, database credentials, or transaction permissions. It acts solely as an isolated secondary reader.
2. **The LLM can only ADD risk:** If the LLM flags an attack, risk increases. If the LLM passes an input, the request is still subject to strict deterministic code-level provenance and limits. The model cannot bypass or override a code rule.
3. **Deterministic Value Provenance:** Extracted monetary figures and payee identities must exist as unambiguous literal token spans in the raw user input.
4. **No LLM-Rendered Confirmation:** Every user confirmation dialog and execution payload is rendered strictly from code-compiled JSON objects.

---

## 2. Five-Layer Defense Pipeline

```
[Untrusted User Input]
         │
         ▼
┌──────────────────┐
│  Layer 1: CLEAN  │ ──► NFKC normalize, strip invisibles, fold homoglyphs, decode base64/hex
└────────┬─────────┘
         │ (Canonical Text + Scan Buffers)
         ▼
┌──────────────────┐
│ Layer 2: SCREEN  │ ──► Isolate Memo, Whitelist chars, Regex policy engine, Banking grammar
└────────┬─────────┘
         │ (Command Text Only; Memo strictly stripped)
         ▼
┌──────────────────┐
│  Layer 3: READ   │ ──► Quarantined LLM inside Boundary Nonce + Canary Token (Fail-Closed)
└────────┬─────────┘
         │ (Extracted Targets + Attack Flags)
         ▼
┌──────────────────┐
│ Layer 4: VERIFY  │ ──► Literal Substring Provenance Engine (Token Spans) + Account Caps
└────────┬─────────┘
         │ (Approved Intent & Verified Entities)
         ▼
┌──────────────────┐
│  Layer 5: SIGN   │ ──► HMAC-SHA256 Signed Mandate + Code-Rendered UI Confirmation
└────────┬─────────┘
         │
         ▼
[Mock Banking Core: Anti-Replay & Balance Ledger]
```

### Layer 1: Clean (`src/clean.py`)
- Normalizes Unicode using the NFKC standard.
- Strips zero-width (`\u200B`, `\uFEFF`), bidirectional, and unprintable control characters.
- Folds Cyrillic and Greek homoglyphs (e.g., Cyrillic `і`, `о`, `е` $\rightarrow$ Latin `i`, `o`, `e`).
- Recursively decodes nested Base64, Hexadecimal, and URL encoding up to a depth of 3.
- Evaluates Shannon character entropy on long tokens (>4.2 bits/char) to catch compressed or encrypted attack buffers.

### Layer 2: Screen (`src/screen.py`)
- **Memo Isolation:** Identifies inline markers (`memo:`, `note:`, `ref:`, trailing `for ...`) and removes them from the command text. The memo is quarantined into a separate alphanumeric field (max 60 chars) and **NEVER** enters the LLM prompt.
- **Memo Sanitization:** Throws `MEMO_INJECTION` if the memo contains imperative transfer verbs (`pay Charlie $100`), system role tags (`SYSTEM:`, `[INST]`), or override directives.
- **Policy Rule Engine:** Compiles regex rules from `config/policy.yaml` targeting persona jailbreaks (DAN), administrative overrides (Regulation E Exception Clause 4), prompt exfiltration, and chat template tokens. Benign usages of *"cancel"* or *"execute"* in ordinary account inquiries do not trigger false positives.
- **Strict Banking Grammar:** Validates standard rigid grammar for balance inquiries and single transfers with polite prefixes and light Hinglish fillers.

### Layer 3: Read (`src/read.py`)
- Isolates the user command inside a dynamic, high-entropy per-request boundary nonce:
  `<user_boundary_3f9a2e> ... </user_boundary_3f9a2e>`
- Embeds a per-request canary token in the system instructions:
  `CANARY_SEC_TOKEN_{canary_id}`
- If the model leaks the canary token, the request is immediately terminated as `DATA_EXFILTRATION`.
- If the user attempts to close or forge boundary nonces, the request terminates as `PROMPT_INJECTION`.
- Strict timeout of 3.0 seconds; on timeout, network error, or offline configuration (`LLM_MODE=offline`), falls back closed into deterministic grammar-only mode with `degraded_mode=True`.

### Layer 4: Verify (`src/verify.py`)
- **Literal Provenance Engine:** Inspects the original **RAW** user string directly (not decoded text or LLM summaries).
- Locates numeric literals (`₹500`, `Rs. 1,000`, `5k`, `2 lakh`, words like `"twenty"`).
- Locates saved payees (`Alice Sharma`, `Bob Verma`, `Charlie Patel`) and their aliases.
- **Ambiguity Gate:** If zero or multiple candidate amounts or payees are detected (such as value swaps: *"send 20... add a zero make it 200"*), the transaction is marked `BLOCKED_AMBIGUOUS` with zero execution risk.
- **Financial Controls:** Enforces per-transfer limits (₹10,000), session cumulative caps (₹25,000), transfer counts (max 5 per session), and sufficient funds.

### Layer 5: Sign (`src/mandate.py`)
- Only executed if the request is `APPROVED` with a deterministic risk score $< 30$ and zero rule hits.
- Constructs an immutable canonical JSON transaction mandate.
- Generates an HMAC-SHA256 cryptographic signature using `MANDATE_SECRET`.
- Produces a deterministic, code-rendered confirmation sentence for the user interface.

---

## 3. Cryptographic Mandate & Mock Banking Core

Transactions cannot be executed via natural language directly. Downstream execution requires submitting the verified mandate to `/api/execute`:

```json
{
  "mandate": {
    "payload": {
      "request_id": "REQ_B891A42F90",
      "intent": "TRANSFER",
      "amount": 500.0,
      "currency": "INR",
      "payee_id": "PAYEE_01",
      "payee_name": "Alice Sharma",
      "memo": "Dinner share",
      "issued_at": "2026-10-11T06:00:00Z"
    },
    "payload_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "signature": "9b12a81...d40c"
  }
}
```

The Mock Banking Core (`src/mock_bank.py`):
1. Recomputes the HMAC-SHA256 signature across the canonical JSON payload bytes. If any field (e.g. `amount` or `payee_id`) was modified, returns `TAMPER_DETECTED`.
2. Inspects an in-memory set of executed `request_id`s. If the same mandate is submitted more than once, returns `REPLAY_DETECTED`.
3. Verifies sufficient account balance before debiting.
