from concurrent.futures import ThreadPoolExecutor
import logging
import queue
import shiboken6
import threading
from concurrent.futures import Future
from PySide6.QtCore import QObject, QTimer, Signal
from typing import Callable

logger = logging.getLogger(__name__)


class BackgroundTask(QObject):
    """Runs a background function in a thread pool while updating the GUI via signals.

    The `progressed` signal emits progress messages (str). The `completed` signal
    emits the `concurrent.futures.Future` whose `result()` contains the task's
    return value or whose `exception()` returns the raised exception.
    """
    progressed = Signal(str)
    completed = Signal(Future)

    def __init__(self, executor: ThreadPoolExecutor, name: str = "Background task", poll_interval: int = 200):
        super().__init__()
        self._progress_q = queue.Queue()
        self._cancel_event = threading.Event()
        self._future = None

        self._executor = executor
        self._name = name
        # parent the QTimer to this QObject to ensure proper cleanup
        self._timer = QTimer(self)
        self._timer.setInterval(poll_interval)
        self._timer.timeout.connect(self._poll_q)

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def run(self, fn: Callable, *args, **kwargs) -> Future:
        assert not self._timer.isActive(), "BackgroundTask already running"
        assert self._progress_q.empty(), "Progress queue not drained"
        assert self._future is None, "BackgroundTask future not None"
        self._cancel_event.clear()

        def progress(msg):
            self._progress_q.put(msg)

        def submission():
            return fn(progress, self.is_cancelled, *args, **kwargs)

        # submit the worker to the provided executor; it should return a Future
        self._future = self._executor.submit(submission)
        self._timer.start()
        return self._future

    def _poll_q(self) -> None:
        assert shiboken6.isValid(self), "BackgroundTask is not valid"
        while not self._progress_q.empty():
            msg = self._progress_q.get_nowait()
            self.progressed.emit(msg)
        if self._future is not None and self._future.done():
            try:
                self._timer.stop()
            except Exception:
                pass
            future = self._future
            # Make _future None here in case the completed signal handler calls run() again
            self._future = None
            self.completed.emit(future)

