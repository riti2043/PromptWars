# Bankism Prompt Changelog

## [v1.0.0] - 2026-10-11

### Added
- Initial quarantined reader prompt `qllm_v1.txt`.
- Dynamic `{canary_id}` injection to detect direct data exfiltration attempts. If the model echoes this token, the gateway halts execution and classifies the attack as `DATA_EXFILTRATION`.
- Dynamic per-request boundary nonce `<user_boundary_{nonce}>` surrounding the untrusted input. If an attacker attempts to craft or close boundary tags, execution triggers a prompt injection fault.
- Strict JSON output schema enforcing typed fields: `intent`, `amount`, `payee`, `attack_flag`, `attack_category`, and `confidence`.
- Explicit negative constraint: untrusted input has zero execution authority.
