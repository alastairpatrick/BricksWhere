from model.rebrickable import SyncCancelled
from viewmodel import SyncViewModel
from concurrent.futures import ThreadPoolExecutor
import threading
import pytest


@pytest.mark.schema
def test_sync_viewmodel_runs_and_reports(monkeypatch, sqlite_db):
    db, conn = sqlite_db

    def fake_sync(conn_arg, urls, progress, is_cancelled):
        # simulate writing a part and reporting progress
        progress("Downloading colors.csv.gz")
        cur = conn_arg.cursor()
        cur.execute("INSERT INTO parts (part_num, name) VALUES (?,?)", ("PX", "TestPart"))
        conn_arg.commit()
        progress("Finished colors")

    # patch the sync_all used by SyncViewModel
    import viewmodel.sync_viewmodel as svmod
    monkeypatch.setattr(svmod, "sync_all", fake_sync)

    collected = []
    def progress_cb(msg):
        collected.append(msg)

    executor = ThreadPoolExecutor(max_workers=1)
    vm = SyncViewModel(str(db), executor)
    # run synchronously for test
    vm.start_sync(progress_cb, lambda: False)

    assert any(m.startswith("Downloading") for m in collected)


@pytest.mark.schema
def test_syncviewmodel_cancel(monkeypatch, sqlite_db):
    db, conn = sqlite_db

    def fake_sync(conn_arg, urls, progress, is_cancelled):
        # block until cancel requested
        while not is_cancelled():
            pass
        raise SyncCancelled()

    import viewmodel.sync_viewmodel as svmod
    monkeypatch.setattr(svmod, "sync_all", fake_sync)

    collected = []
    def progress_cb(msg):
        collected.append(msg)

    executor = ThreadPoolExecutor(max_workers=1)
    vm = SyncViewModel(str(db), executor)

    cancel_event = threading.Event()

    # run start_sync in a background thread so we can cancel it
    def runner():
        vm.start_sync(progress_cb, cancel_event.is_set)

    t = threading.Thread(target=runner)
    t.start()
    # request cancellation
    cancel_event.set()
    t.join(timeout=2)

    # ensure progress includes SUMMARY: Sync cancelled (emitted by start_sync)
    assert any("SUMMARY: Sync cancelled" in m for m in collected)
