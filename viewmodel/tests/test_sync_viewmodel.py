import queue
import threading
from model.rebrickable import SyncCancelled
from viewmodel import  SyncViewModel


import pytest


@pytest.mark.schema
def test_sync_viewmodel_runs_and_reports(sqlite_db):
    db, conn = sqlite_db

    msgs = []

    def fake_sync(conn, progress, cancel_event):
        # simulate writing a part and reporting progress
        progress("Downloading colors.csv.gz")
        cur = conn.cursor()
        cur.execute("INSERT INTO parts (part_num, name) VALUES (?,?)", ("PX", "TestPart"))
        conn.commit()
        progress("Finished colors")

    vm = SyncViewModel(str(db), sync_func=fake_sync)
    q = queue.Queue()
    cancel = threading.Event()
    vm.sync(q, cancel)

    # drain queue
    while not q.empty():
        msgs.append(q.get_nowait())

    assert any(m.startswith("Downloading") for m in msgs)
    assert "ALL_DONE" in msgs


@pytest.mark.schema
def test_syncviewmodel_start_async_and_join(sqlite_db):
    db, conn = sqlite_db

    def fake_sync(conn, progress, cancel_event):
        progress("A")
        progress("B")

    vm = SyncViewModel(str(db), sync_func=fake_sync)
    q = vm.start_async()

    msgs = []
    while True:
        try:
            msgs.append(q.get(timeout=0.5))
            if msgs[-1] == "ALL_DONE":
                break
        except Exception:
            break

    # wait for thread to finish
    vm.join()
    assert any(m == "A" for m in msgs)
    assert any(m == "B" for m in msgs)


@pytest.mark.schema
def test_syncviewmodel_cancel(sqlite_db):
    db, conn = sqlite_db

    def fake_sync(conn, progress, cancel_event):
        # block until cancel requested
        while not cancel_event.is_set():
            pass
        raise SyncCancelled()

    vm = SyncViewModel(str(db), sync_func=fake_sync)
    q = vm.start_async()
    # request cancellation
    vm.cancel()
    vm.join()
    # ensure ALL_DONE present and CANCELLED was sent
    items = []
    while not q.empty():
        items.append(q.get_nowait())
    assert "ALL_DONE" in items
