"""Private Permissioned Blockchain Ledger for Video Evidence Chain of Custody.

This module implements a lightweight, tamper-proof private ledger simulation
designed for mathematical proof of video snapshot integrity without mining,
cryptocurrency, or proof-of-work overhead.
"""

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class Block:
    """Represents a single immutable record block in the evidence blockchain."""

    def __init__(
        self,
        index: int,
        timestamp: str,
        data: Dict[str, Any],
        previous_hash: str,
        current_hash: Optional[str] = None,
    ):
        self.index = index
        self.timestamp = timestamp
        self.data = data
        self.previous_hash = previous_hash
        self.hash = current_hash if current_hash is not None else self.calculate_hash()

    def calculate_hash(self) -> str:
        """Deterministically calculate SHA-256 digest of block contents."""
        block_payload = {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
        }
        serialized = json.dumps(block_payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert block instance to serializable dictionary."""
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Block":
        """Reconstruct a Block instance from dictionary."""
        return cls(
            index=data["index"],
            timestamp=data["timestamp"],
            data=data["data"],
            previous_hash=data["previous_hash"],
            current_hash=data["hash"],
        )

    def __repr__(self) -> str:
        return f"<Block #{self.index} hash={self.hash[:12]}... prev={self.previous_hash[:12]}...>"


class PrivateBlockchain:
    """Modular private permissioned ledger for storing cryptographic evidence hashes."""

    def __init__(self, ledger_file: Optional[str] = None):
        self.chain: List[Block] = []
        self._lock = threading.RLock()
        self.ledger_file = ledger_file
        self.initialize_chain()

    def create_genesis_block(self) -> Block:
        """Create and return the deterministic genesis block."""
        return Block(
            index=0,
            timestamp="2026-01-01T00:00:00+00:00",
            data={
                "type": "GENESIS",
                "message": "IBVAP Chain of Custody Initialized",
                "authority": "National Border Surveillance Security Authority",
            },
            previous_hash="0" * 64,
        )

    def initialize_chain(self) -> None:
        """Load ledger from persistence file if available, or create genesis block."""
        with self._lock:
            if self.ledger_file and os.path.isfile(self.ledger_file):
                try:
                    with open(self.ledger_file, "r", encoding="utf-8") as f:
                        records = json.load(f)
                    if isinstance(records, list) and len(records) > 0:
                        loaded = [Block.from_dict(r) for r in records]
                        # Verify integrity of existing loaded file
                        valid, error = self._validate_chain_list(loaded)
                        if valid:
                            self.chain = loaded
                            return
                        else:
                            print(f"[WARN] Persisted blockchain failed integrity check: {error}. Rebuilding from genesis.")
                except Exception as exc:
                    print(f"[WARN] Could not load ledger from {self.ledger_file}: {exc}")

            # Default: initialize with genesis block
            self.chain = [self.create_genesis_block()]
            self._persist()

    def get_latest_block(self) -> Block:
        """Return the most recently anchored block."""
        with self._lock:
            return self.chain[-1]

    def add_block(
        self,
        data: Dict[str, Any],
        timestamp: Optional[str] = None,
        previous_hash: Optional[str] = None,
    ) -> Block:
        """Add a new block containing evidence metadata and cryptographic hash.

        Args:
            data: Payload dictionary, typically containing {"image_hash": ..., "camera_id": ...}
            timestamp: Optional ISO datetime string (defaults to current UTC time).
            previous_hash: Optional previous hash string (defaults to last block's hash).

        Returns:
            The newly created and appended Block.
        """
        with self._lock:
            latest = self.get_latest_block()
            ts = timestamp or datetime.now(timezone.utc).isoformat()
            prev = previous_hash if previous_hash is not None else latest.hash

            new_block = Block(
                index=len(self.chain),
                timestamp=ts,
                data=data,
                previous_hash=prev,
            )
            self.chain.append(new_block)
            self._persist()
            return new_block

    def is_chain_valid(self) -> Tuple[bool, Optional[str]]:
        """Validate cryptographic integrity of the entire ledger.

        Ensures:
        1. Genesis block is intact.
        2. Every block's calculated hash matches its stored hash.
        3. Every block's previous_hash correctly points to the prior block's hash.

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        with self._lock:
            return self._validate_chain_list(self.chain)

    @staticmethod
    def _validate_chain_list(chain_blocks: List[Block]) -> Tuple[bool, Optional[str]]:
        if not chain_blocks:
            return False, "Chain is empty."

        genesis = chain_blocks[0]
        if genesis.index != 0 or genesis.previous_hash != "0" * 64:
            return False, "Genesis block is corrupted or has invalid previous hash."

        if genesis.hash != genesis.calculate_hash():
            return False, "Genesis block content hash mismatch."

        for i in range(1, len(chain_blocks)):
            curr = chain_blocks[i]
            prev = chain_blocks[i - 1]

            if curr.index != i:
                return False, f"Block index sequence broken at index {curr.index} (expected {i})."

            if curr.previous_hash != prev.hash:
                return False, (
                    f"Cryptographic link broken between Block #{prev.index} and Block #{curr.index}: "
                    f"previous_hash '{curr.previous_hash}' does not match prior block hash '{prev.hash}'."
                )

            recalculated = curr.calculate_hash()
            if curr.hash != recalculated:
                return False, (
                    f"Block #{curr.index} content has been tampered! "
                    f"Stored hash '{curr.hash}' does not match recalculated hash '{recalculated}'."
                )

        return True, None

    def find_block_by_image_hash(self, image_hash: str) -> Optional[Block]:
        """Search the blockchain for a block recording the exact image hash."""
        with self._lock:
            clean_hash = image_hash.strip().lower()
            for block in self.chain:
                if block.data and block.data.get("image_hash", "").lower() == clean_hash:
                    return block
            return None

    def get_chain(self) -> List[Dict[str, Any]]:
        """Return the entire blockchain as a list of dictionaries."""
        with self._lock:
            return [b.to_dict() for b in self.chain]

    def _persist(self) -> None:
        """Persist current chain state to JSON ledger file."""
        if not self.ledger_file:
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.ledger_file)), exist_ok=True)
            with open(self.ledger_file, "w", encoding="utf-8") as f:
                json.dump([b.to_dict() for b in self.chain], f, indent=2)
        except Exception as exc:
            print(f"[WARN] Failed to write ledger file: {exc}")


# Singleton instance shared across FastAPI application
_ledger_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "blockchain_ledger.json")
)
blockchain_ledger = PrivateBlockchain(ledger_file=_ledger_path)
