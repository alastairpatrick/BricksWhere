import time
import pytest

from viewmodel.background_task import BackgroundTask


def _wait_for(app, predicate, timeout=2.0):
    """Spin wait while processing Qt events until predicate() is True or timeout."""
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


# NOTE: these tests rely on a single session-scoped QApplication provided by the
# `app_qt` fixture in `conftest.py`. Tests must not create additional
# QApplication instances (or create one inside `_wait_for`) because multiple
# QApplications in the same process can cause races and native crashes on
# some platforms; the `app_qt` fixture ensures a single, shared application.


def test_backgroundtask_success(executor, app_qt):
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
    bt.completed.connect(lambda future: completed.append(future))

    def worker(progress, is_cancelled):
        progress("step1")
        progress("step2")
        # normal return
        return 7

    bt.run(worker)

    assert _wait_for(app_qt, lambda: len(completed) > 0), "timed out waiting for completion"
    assert completed[0].result() == 7
    assert progressed == ["step1", "step2"]


def test_backgroundtask_exception(executor, app_qt):
    bt = BackgroundTask(executor, poll_interval=10)

    progressed = []
    completed = []
    bt.progressed.connect(lambda m: progressed.append(m))
    bt.completed.connect(lambda ok: completed.append(ok))

    def worker(progress, is_cancelled):
        progress("before error")
        raise RuntimeError("boom")

    bt.run(worker)

    assert _wait_for(app_qt, lambda: len(completed) > 0), "timed out waiting for completion"
    assert str(completed[0].exception()) == "boom"
    assert progressed == ["before error"]


def test_backgroundtask_cancel(executor, app_qt):
    bt = BackgroundTask(executor, poll_interval=10)

    progressed = []
    completed = []
    bt.progressed.connect(lambda m: progressed.append(m))
    bt.completed.connect(lambda ok: completed.append(ok))

    def worker(progress, is_cancelled):
        assert is_cancelled()
        raise RuntimeError("cancelled")

    bt.run(worker)
    # There isn't a race here; in unit tests, the FakeExecutor doesn't
    # run submitted tasks until the event loop is processed...
    bt.cancel()

    # ... which happens inside _wait_for
    assert _wait_for(app_qt, lambda: len(completed) > 0), "timed out waiting for completion"
    assert str(completed[0].exception()) == "cancelled"