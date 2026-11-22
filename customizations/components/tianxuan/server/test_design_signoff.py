"""Two service connections racing to sign the same document revision."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from tianxuan_core import NotFound, PermissionDenied, Tianxuan, VersionConflict


def test_competing_signers_and_historical_receipt(tmp_path):
    path = str(tmp_path / "business.sqlite")
    first = Tianxuan(path)
    second = Tianxuan(path)
    try:
        owner = first.register("Studio", "author@example.invalid", "local-test-password")["user_id"]
        editor = first.add_member(owner, "editor@example.invalid", "local-test-password")["user_id"]
        outsider = first.register("Other Studio", "other@example.invalid", "local-test-password")["user_id"]
        key = first.create_doc(owner, "Gate", "Pull once.")["id"]
        first.update_doc(owner, key, "Pull twice.", 1)
        ready = Barrier(2)

        def sign(store, actor):
            ready.wait(timeout=5)
            try:
                return store.design_signoff(actor, key, 1, "One pull opens the gate.")
            except VersionConflict:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(sign, [first, second], [owner, editor]))
        assert results.count(None) == 1
        receipt = first.design_signoff(owner, key, 1)
        assert receipt and receipt in results and receipt["confirmed_by"] in {owner, editor}
        assert second.design_signoff(receipt["confirmed_by"], key, 1, receipt["acceptance"]) == receipt
        assert second.design_signoff(owner, key, 2) is None
        with pytest.raises(NotFound):
            second.design_signoff(outsider, key, 1)
        first.set_visibility(owner, key, "private")
        with pytest.raises(PermissionDenied):
            second.design_signoff(editor, key, 1)
        with pytest.raises(PermissionDenied):
            second.design_signoff(editor, key, 2, "Two pulls open the gate.")
    finally:
        first.db.close()
        second.db.close()
