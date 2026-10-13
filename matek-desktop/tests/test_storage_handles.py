from pathlib import Path
from companion.costs import CostLedger
from companion.storage import ConversationStore


def test_closed_database_handles_can_be_removed(tmp_path):
    ledger_path = tmp_path / "usage.db"
    ledger = CostLedger(ledger_path, Path("config/pricing.json"))
    assert not ledger.history()
    assert ledger.totals() == (0, 0)
    ledger_path.unlink()
    store_path = tmp_path / "history.db"
    store = ConversationStore(store_path)
    store.save("Test", "Answer", 7)
    store.read()
    store.clear()
    store_path.unlink()
