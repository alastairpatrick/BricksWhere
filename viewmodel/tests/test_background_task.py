import time
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtWidgets import QApplication
import pytest

from viewmodel.background_task import BackgroundTask


def _wait_for(predicate, timeout=2.0):
    """Spin wait while processing Qt events until predicate() is True or timeout."""
    app = QApplication.instance() or QApplication([])
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        # allow Qt to process timers/signals
        try:
            app.processEvents()
        except Exception:
            pass
        time.sleep(0.01)
    return False


def test_backgroundtask_success():
    executor = ThreadPoolExecutor(max_workers=1)
    bt = BackgroundTask(executor, poll_interval=10)

    # drain any leftover messages
    try:
        while not bt._progress_q.empty():
            bt._progress_q.get_nowait()
    except Exception:
        pass

    progressed = []
    completed = []

    bt.progressed.connect(lambda m: progressed.append(m))
    bt.completed.connect(lambda ok: completed.append(ok))

    def worker(progress, is_cancelled):
        progress("step1")
        progress("step2")
        # normal return

    bt.run(worker)

    assert _wait_for(lambda: len(completed) > 0), "timed out waiting for completion"
    assert completed[0] is True
    assert progressed == ["step1", "step2"]

    executor.shutdown(wait=True)


def test_backgroundtask_exception():
    executor = ThreadPoolExecutor(max_workers=1)
    bt = BackgroundTask(executor, poll_interval=10)

    progressed = []
    completed = []
    bt.progressed.connect(lambda m: progressed.append(m))
    bt.completed.connect(lambda ok: completed.append(ok))

    def worker(progress, is_cancelled):
        progress("before error")
        raise RuntimeError("boom")

    bt.run(worker)

    assert _wait_for(lambda: len(completed) > 0), "timed out waiting for completion"
    assert completed[0] is False
    assert progressed == ["before error"]

    executor.shutdown(wait=True)


def test_backgroundtask_cancel():
    executor = ThreadPoolExecutor(max_workers=1)
    bt = BackgroundTask(executor, poll_interval=10)

    progressed = []
    completed = []
    bt.progressed.connect(lambda m: progressed.append(m))
    bt.completed.connect(lambda ok: completed.append(ok))

    def worker(progress, is_cancelled):
        # busy loop until cancelled
        while not is_cancelled():
            time.sleep(0.01)
        # signal that worker observed cancel and raise to indicate cancelled
        raise RuntimeError("cancelled")

    bt.run(worker)

    # request cancel shortly after starting
    time.sleep(0.05)
    bt.cancel()

    assert _wait_for(lambda: len(completed) > 0), "timed out waiting for completion"
    assert completed[0] is False

    executor.shutdown(wait=True)
