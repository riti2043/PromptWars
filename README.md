# Bankism — Deterministic-First AI Firewall & Mandate Gateway

[![License: MIT](https://img.shields.io/badge/License-MIT-teal.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Docker Ready](https://img.shields.io/badge/Docker-Cloud%20Run%20Ready-2496ED.svg)](Dockerfile)

> **Core Thesis:** *The LLM drafts, code proves, the user signs.*  
> Bankism sits between untrusted natural language user inputs and banking/payment APIs. It is a **product**, not a chatbot: one structured request in, one deterministic verdict out, no model-written UI text, and zero function-calling authority for the LLM.

---

## Key Security Innovations

1. **Literal Provenance Engine:** Proves that extracted transaction amounts and payees exist as literal token spans in raw user input. Ambiguous candidates (>1 or 0) fail closed with `BLOCKED_AMBIGUOUS`.
2. **Trojan Memo Isolation:** Transaction memos are quarantined from LLM prompts and sanitized against an alphanumeric whitelist. Memos with imperative verbs trigger `MEMO_INJECTION`.
3. **Detection-Independent Safety:** Even if an LLM is completely compromised, unauthorized transactions cannot execute because code proves literal provenance.
4. **Cryptographic Mandates:** Approved transactions generate HMAC-SHA256 signed canonical JSON mandates. The mock banking core enforces anti-replay and tamper resistance.
5. **Fail-Closed Degraded Mode:** On LLM timeout (>3s), rate-limit, or offline mode, falls back closed to deterministic grammar-only mode without network dependencies.
6. **Sub-Millisecond Latency:** Average $p50$ latency is **0.20 ms** with a **100% attack block rate** on 125 authentic test cases.

---

## Empirical Benchmark Scorecard (125 Cases)

| Metric | Measured Value | Target | Status |
| :--- | :--- | :--- | :--- |
| **Attack Block Rate** | **100.0%** | > 95% | **PASS** |
| **Benign False Positive Rate** | **0.0%** | < 5% | **PASS** |
| **Determinism Replay (3x)** | **100.0%** | 100% | **PASS** |
| **Latency (p50)** | **0.20 ms** | < 50 ms | **PASS** |
| **Latency (p95)** | **0.57 ms** | < 100 ms | **PASS** |

*All results generated deterministically via `python -m tests.run_eval` and saved in `static/results.json` and `docs/results.md`.*

---

## Quickstart: Run Locally

### 1. Clone & Set Up Environment
```bash
git clone https://github.com/riti2043/PromptWars.git
cd PromptWars

# Create Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install pinned dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

### 2. Run the Gateway Server
```bash
# Starts Bankism in offline degraded mode by default
uvicorn src.main:app --host 0.0.0.0 --port 8000
```
Open **`http://127.0.0.1:8000`** in your browser to interact with the restrained frosted-glass console, run the 9-step Tour Mode, or test presets 1–8.

### 3. Run Test & Evaluation Harness
```bash
# Run unit test suite
python -m pytest -v

# Run live gateway smoke test
python scripts/smoke_test.py http://127.0.0.1:8000

# Run 125-case evaluation benchmark
python -m tests.run_eval
```

---

## Deploying to Google Cloud Run

Bankism is packaged as a lightweight, production-grade container with a non-root user and automated `/healthz` checks. Because the mock banking state and audit log are stored in memory, Cloud Run should be configured with `--max-instances 1` and `--min-instances 1` for demo stability.

### Step 1: Install Google Cloud SDK & Login
Ensure you have the Google Cloud CLI (`gcloud`) installed and authenticated:
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### Step 2: Store Secrets in Secret Manager (Recommended)
```bash
# Create Mandate Secret
echo -n "bankism_prod_hmac_secret_key_2026_xyz" | \
  gcloud secrets create bankism-mandate-secret --data-file=-

# (Optional) Store Gemini API Key for live LLM mode
echo -n "YOUR_GEMINI_API_KEY" | \
  gcloud secrets create bankism-gemini-key --data-file=-
```

### Step 3: Build & Deploy to Cloud Run
Deploy directly from source using Google Cloud Build:
```bash
gcloud run deploy bankism \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 1 \
  --max-instances 1 \
  --timeout 30s \
  --set-env-vars LLM_MODE=offline,GEMINI_MODEL=gemini-2.5-flash,DEMO_HARNESS=1 \
  --set-secrets MANDATE_SECRET=bankism-mandate-secret:latest
```

*Note: To enable live Gemini mode on Cloud Run, set `LLM_MODE=live` and supply `--set-secrets GEMINI_API_KEY=bankism-gemini-key:latest`.*

### Step 4: Verify Live Cloud Run URL
Once deployed, Cloud Run will print the Service URL (e.g., `https://bankism-xyz-uc.a.run.app`). Run the automated smoke test against the live endpoint:
```bash
python scripts/smoke_test.py https://bankism-xyz-uc.a.run.app
```

---

## Environment Variables Reference

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `PORT` | `8000` | HTTP port for the Uvicorn server |
| `LLM_MODE` | `offline` | `live` (invokes Gemini via `google-genai`) or `offline` (deterministic grammar-only) |
| `GEMINI_API_KEY` | *(empty)* | Google GenAI API key for quarantined reader |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model name for second reader |
| `MANDATE_SECRET` | *(demo key)* | Secret key for HMAC-SHA256 mandate signing |
| `DEMO_HARNESS` | `1` | Enables `x-simulate-compromised-model` header testing |

---

## Project Directory Layout

```
.
├── config/
│   └── policy.yaml           # Threat categories, weights, limits, and regexes
├── docs/
│   ├── abstract.md           # Problem understanding, strategy, and novelty
│   ├── architecture.md       # Pipeline design, trust boundaries, and mandate flow
│   ├── DATASETS.md           # 125 test cases breakdown and licenses
│   ├── deck_outline.md       # 10-minute jury defence slide-by-slide outline
│   ├── research.md           # State-of-the-art competitive research dossier
│   └── results.md            # Empirical evaluation metrics and failure analysis
├── prompts/
│   ├── CHANGELOG.md          # Prompt engineering and revision log
│   └── qllm_v1.txt           # Quarantined LLM system prompt template with nonce/canary
├── scripts/
│   └── smoke_test.py         # End-to-end verification script for local and live URLs
├── src/
│   ├── clean.py              # Stage 0: NFKC, homoglyphs, decoding, entropy
│   ├── screen.py             # Stage 1: Memo isolation, rule engine, strict grammar
│   ├── read.py               # Stage 2: Quarantined reader with canary & nonce
│   ├── verify.py             # Stage 3: Literal Provenance Engine & banking caps
│   ├── mandate.py            # Stage 4: HMAC signing & code-rendered confirmation
│   ├── mock_bank.py          # In-memory bank core with anti-replay ledger
│   ├── pipeline.py           # 5-layer firewall pipeline orchestrator
│   ├── schemas.py            # Strict Pydantic v2 schemas
│   └── main.py               # FastAPI server with rate limiting & static routes
├── static/
│   ├── app.js                # Console client, Tour mode, and Benchmarks browser
│   ├── faq.json              # Client-side Floating Guide Q&A
│   ├── index.html            # Restrained frosted-glass security console
│   ├── presets.json          # Presets 1-8 for keyboard shortcuts
│   ├── results.json          # Precomputed benchmark scorecard
│   └── style.css             # Glass visual system with WCAG AA contrast
├── tests/
│   ├── build_cases.py        # Generates the 125 authentic test cases
│   ├── cases.json            # Full test suite of 125 cases
│   ├── run_eval.py           # Evaluation runner with 3x determinism replay
│   ├── test_clean.py         # Unit tests for clean layer
│   ├── test_mandate.py       # Unit tests for mandate signing & replay
│   ├── test_pipeline.py      # Unit tests for end-to-end firewall pipeline
│   ├── test_screen.py        # Unit tests for screen layer & safe words
│   └── test_verify.py        # Unit tests for literal provenance engine
├── Dockerfile                # Production Cloud Run container definition
├── LICENSE                   # MIT License
└── requirements.txt          # Pinned dependency manifest
```

---

## Known Limitations

- **Social Engineering:** Bankism protects the API boundary from prompt injection and parameter manipulation; it cannot detect external off-platform fraud where a user willingly authorizes a transfer to an attacker.
- **Client Compromise:** If an attacker gains full root access to the user's client device, hardware-level keylogging is outside the firewall gateway scope.
