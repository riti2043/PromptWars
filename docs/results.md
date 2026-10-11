# Bankism Benchmark & Evaluation Results

**Evaluation Timestamp:** 2026-10-11T06:09:57Z  
**Policy Version:** v1.0.0  
**Execution Mode:** `offline`  
**Dataset Size:** 125 authentic test cases  

---

## Executive Scorecard

| Metric | Measured Value | Standard Target | Status |
| :--- | :--- | :--- | :--- |
| **Attack Block Rate** | **100.0%** | > 95% | **PASS** |
| **Benign False Positive Rate** | **0.0%** | < 5% | **PASS** |
| **Determinism Replay (3x)** | **100.0%** | 100% | **PASS** |
| **Latency (p50)** | **0.2 ms** | < 50 ms | **PASS** |
| **Latency (p95)** | **0.57 ms** | < 100 ms | **PASS** |

---

## Breakdown by Dataset

| Dataset | Total Cases | Blocked | Approved | Accuracy (%) |
| :--- | :--- | :--- | :--- | :--- |
| Bankism Core Suite | 72 | 40 | 32 | 100.0% |
| Financial Hard-Negatives | 18 | 18 | 0 | 100.0% |
| Obfuscation Mutations | 20 | 20 | 0 | 100.0% |
| AgentDojo | 8 | 8 | 0 | 100.0% |
| InjecAgent | 7 | 7 | 0 | 100.0% |

---

## Breakdown by Threat Category

| Threat Category | Total Cases | Correct Verdicts | Accuracy (%) |
| :--- | :--- | :--- | :--- |
| NONE | 32 | 32 | 100.0% |
| OUT_OF_SCOPE | 18 | 18 | 100.0% |
| POLICY_OVERRIDE | 10 | 10 | 100.0% |
| JAILBREAK_ROLEPLAY | 8 | 8 | 100.0% |
| DATA_EXFILTRATION | 6 | 6 | 100.0% |
| MEMO_INJECTION | 16 | 16 | 100.0% |
| OBFUSCATION | 20 | 20 | 100.0% |
| PROMPT_INJECTION | 15 | 15 | 100.0% |

---

## Transparent Failure Analysis

### False Positives (0)
*None. 0 false positives observed on the core benign suite.*

### Missed Attacks (0)
*None. All 93 adversarial test cases were reliably blocked.*
