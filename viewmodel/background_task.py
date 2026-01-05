from concurrent.futures import ThreadPoolExecutor
import logging
import queue
from PySide6.QtCore import QObject, QTimer, Signal
import threading
from typing import Callable

logger = logging.getLogger(__name__)

class BackgroundTask(QObject):
    """Runs a background function in a thread pool, while updating updating GUI via signals."""
    progressed = Signal(str)
    completed = Signal(bool)
    
    def __init__(self, executor: ThreadPoolExecutor, name = "Background task", poll_interval: int = 200):
        super().__init__()
        self._progress_q = queue.Queue()
        self._cancel_event = threading.Event()

        self._executor = executor
        self._name = name
        self._timer = QTimer()
        self._timer.setInterval(poll_interval)
        self._timer.timeout.connect(self._poll_q)

    def cancel(self) -> None:
        self._cancel_event.set()
    
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()
    
    def run(self, fn: Callable, *args, **kwargs) -> None:
        assert not self._timer.isActive(), "BackgroundTask already running"
        assert self._progress_q.empty(), "Progress queue not drained"
        self._cancel_event.clear()
        
        def progress(msg):
            self._progress_q.put(msg)
        def submission():
            try:
                fn(progress, self.is_cancelled, *args, **kwargs)
                self._progress_q.put("DONE_SUCCESS")
            except Exception as e:
                logger.exception("%s failed: %s", self._name, e)
                self._progress_q.put("DONE_FAILURE")

        self._executor.submit(submission)
        self._timer.start()

    def _poll_q(self) -> None:
        while not self._progress_q.empty():
            msg = self._progress_q.get_nowait()
            if msg.startswith("DONE_"):
                self._timer.stop()
                self.completed.emit(msg == "DONE_SUCCESS")
            else:
                self.progressed.emit(msg)
