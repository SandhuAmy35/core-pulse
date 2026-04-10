from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from layer1_vault.src.entropy_journal import EntropyJournal


class EntropyJournalTests(unittest.TestCase):
    def test_append_and_recover_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            journal_path = Path(temp_dir) / "entropy.wal"
            key_material = b"layer1-journal-test-key-0000000000"
            journal = EntropyJournal(journal_path, key_material=key_material)
            first = journal.append_seed(b"a" * 32, request_hash="req-1")
            second = journal.append_seed(b"b" * 32, request_hash="req-2")
            self.assertEqual(first.sequence, 1)
            self.assertEqual(second.sequence, 2)
            self.assertTrue(second.merkle_root)

            recovered = EntropyJournal(journal_path, key_material=key_material)
            self.assertEqual(recovered.state.last_sequence, 2)
            self.assertEqual(recovered.state.last_seed, b"b" * 32)
            self.assertEqual(recovered.state.merkle_root, second.merkle_root)
            self.assertFalse(recovered.state.tail_truncated)

    def test_partial_tail_is_truncated_on_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            journal_path = Path(temp_dir) / "entropy.wal"
            key_material = b"layer1-journal-test-key-0000000000"
            journal = EntropyJournal(journal_path, key_material=key_material)
            entry = journal.append_seed(b"c" * 32, request_hash="req-3")
            _ = entry

            with journal_path.open("ab") as handle:
                handle.write(b"{\"v\":1,\"broken\":")

            recovered = EntropyJournal(journal_path, key_material=key_material)
            self.assertEqual(recovered.state.last_sequence, 1)
            self.assertEqual(recovered.state.last_seed, b"c" * 32)
            self.assertTrue(recovered.state.tail_truncated)

    def test_invalid_mac_record_is_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            journal_path = Path(temp_dir) / "entropy.wal"
            key_material = b"layer1-journal-test-key-0000000000"
            journal = EntropyJournal(journal_path, key_material=key_material)
            first = journal.append_seed(b"d" * 32, request_hash="req-4")
            second = journal.append_seed(b"e" * 32, request_hash="req-5")
            _ = second

            lines = journal_path.read_text(encoding="utf-8").splitlines()
            tampered = json.loads(lines[1])
            tampered["mac_hex"] = "0" * 64
            lines[1] = json.dumps(tampered, sort_keys=True, separators=(",", ":"))
            journal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            recovered = EntropyJournal(journal_path, key_material=key_material)
            self.assertEqual(recovered.state.last_sequence, 1)
            self.assertEqual(recovered.state.last_seed, b"d" * 32)
            self.assertEqual(recovered.state.merkle_root, first.merkle_root)
            self.assertTrue(recovered.state.tail_truncated)


if __name__ == "__main__":
    unittest.main()
