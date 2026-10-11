"""
mock_bank.py: In-memory mock core banking system.
- Tracks balance, daily limits, session count, and processed request IDs.
- Contains 3 saved payees with aliases.
- Accepts only cryptographically verified mandates.
- Strictly rejects repeated request_ids (anti-replay) and tampered payloads.
- Provides a clean reset method.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime

DEFAULT_SAVED_PAYEES = [
    {
        "id": "PAYEE_01",
        "name": "Alice Sharma",
        "aliases": ["Alice", "Alice S", "alice@okhdfcbank"],
        "account_number": "XXXX-XXXX-1029",
        "upi_id": "alice@okhdfcbank"
    },
    {
        "id": "PAYEE_02",
        "name": "Bob Verma",
        "aliases": ["Bob", "Bob V", "bob@axisbank"],
        "account_number": "XXXX-XXXX-4491",
        "upi_id": "bob@axisbank"
    },
    {
        "id": "PAYEE_03",
        "name": "Charlie Patel",
        "aliases": ["Charlie", "Charlie P", "charlie@icici"],
        "account_number": "XXXX-XXXX-8820",
        "upi_id": "charlie@icici"
    }
]

INITIAL_BALANCE = 50000.00

class MockBank:
    def __init__(self):
        self.reset()

    def reset(self):
        self.user_name = "Rithvik M."
        self.account_id = "ACC-99214-IN"
        self.balance = INITIAL_BALANCE
        self.saved_payees = list(DEFAULT_SAVED_PAYEES)
        self.session_transfers = 0
        self.session_spent = 0.00
        self.executed_mandate_ids = set()
        self.transactions = []

    def get_account_summary(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "user_name": self.user_name,
            "currency": "INR",
            "balance": round(self.balance, 2),
            "session_spent": round(self.session_spent, 2),
            "session_transfers": self.session_transfers,
            "saved_payees": self.saved_payees,
            "recent_transactions": self.transactions[-5:]
        }

    def execute_mandate(self, mandate_payload: Dict[str, Any], signature: str) -> Dict[str, Any]:
        """
        Execute an approved transfer mandate. Rejects replay and tampering.
        """
        from .mandate import verify_mandate_signature

        req_id = mandate_payload.get("request_id")
        if not req_id:
            return {"success": False, "error": "Missing request_id in mandate"}

        # Anti-replay check
        if req_id in self.executed_mandate_ids:
            return {
                "success": False,
                "error": "REPLAY_DETECTED: Mandate has already been executed."
            }

        # Cryptographic verification
        if not verify_mandate_signature(mandate_payload, signature):
            return {
                "success": False,
                "error": "TAMPER_DETECTED: Mandate cryptographic signature is invalid."
            }

        amount = float(mandate_payload.get("amount", 0.0))
        if amount > self.balance:
            return {
                "success": False,
                "error": f"INSUFFICIENT_FUNDS: Available balance ₹{self.balance:.2f} < ₹{amount:.2f}"
            }

        # Deduct balance and update state
        self.balance -= amount
        self.session_spent += amount
        self.session_transfers += 1
        self.executed_mandate_ids.add(req_id)

        tx_record = {
            "tx_id": f"TXN_{len(self.transactions) + 1001}",
            "request_id": req_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "amount": amount,
            "payee_name": mandate_payload.get("payee_name"),
            "memo": mandate_payload.get("memo"),
            "remaining_balance": round(self.balance, 2)
        }
        self.transactions.append(tx_record)

        return {
            "success": True,
            "receipt": {
                "tx_id": tx_record["tx_id"],
                "amount": amount,
                "currency": mandate_payload.get("currency", "INR"),
                "payee_name": mandate_payload.get("payee_name"),
                "memo": mandate_payload.get("memo"),
                "timestamp": tx_record["timestamp"],
                "remaining_balance": round(self.balance, 2)
            }
        }

# Global singleton in-memory bank instance
bank_instance = MockBank()
