# Bankism Datasets & Benchmark Specifications

All benchmark datasets used in the Bankism evaluation suite (`tests/cases.json`) are cataloged below with their source origins, sample counts, and licensing terms.

---

## 1. Dataset Catalog

| Dataset Name | Cases | Origin / Source | License | Scope & Description |
| :--- | :--- | :--- | :--- | :--- |
| **Bankism Core Suite (Benign)** | 32 | Bankism Engineering | Proprietary (MIT Repo License) | Authentic everyday banking requests: balance inquiries, single transfers, polite prefixes, number words, lakh/k notations, and Hinglish phrasing (`karo`). |
| **Bankism Core Suite (Attacks)** | 40 | Bankism Security Research | Proprietary (MIT Repo License) | Direct prompt injection, DAN/developer-mode roleplay jailbreaks, Federal Regulation E authority mimicry, value swaps, exfiltration attempts, and Trojan memo injections. |
| **Financial Hard-Negatives** | 18 | Bankism Engineering | Proprietary (MIT Repo License) | Legitimate non-transaction banking inquiries containing high-risk keywords (*cancel*, *override*, *execute*, *force*, *terminate*). Designed to stress-test false-positive resistance. |
| **Obfuscation Mutations** | 20 | Generated Mutations | Proprietary (MIT Repo License) | Synthetically mutated attack payloads using zero-width spaces (`\u200B`), Cyrillic homoglyphs (`\u0456gn\u043er\u0435`), Base64 payloads, Hex strings, URL encoding, and high-entropy blobs. |
| **AgentDojo (Adapted Samples)** | 8 | Adapted from ETH Zurich / Invariant Labs (`ethz-spylab/agentdojo`) | **MIT License** | Indirect injection vectors embedded in simulated emails, account statements, and calendar invites. |
| **InjecAgent (Adapted Samples)** | 7 | Adapted from UIUC (`uiuc-kang-lab/InjecAgent`) | **MIT License** | Indirect prompt injection payloads targeting tool-integrated autonomous agents (webhooks, database lookup returns). |

---

## 2. Integrity & Licensing Declarations

- **Total Test Cases:** 125
- **Public Adaptations:** All adapted samples from AgentDojo and InjecAgent are licensed under the **MIT License**.
- **No Fabricated Benchmarks:** Precomputed figures in `static/results.json` and `docs/results.md` are generated directly by running `python -m tests.run_eval` against the real Bankism pipeline.
- **HarmBench / PINT Exclusions:** HarmBench was excluded per specification constraints. PINT was omitted because its raw evaluation splits require external authentication that cannot be redistributed under open terms.
