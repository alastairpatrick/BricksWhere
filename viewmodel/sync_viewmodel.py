import queue
import threading
from typing import Callable

from model.db import create_connection, connection_ctx
from model.rebrickable import SyncCancelled, sync_all


class SyncViewModel:
    """Encapsulate synchronization logic so it can be tested.

    The view-model sends progress messages to a queue and obeys an external
    cancel_event. A custom sync_func may be injected for testing.
    """
    def __init__(self, db_path: str = "data.db", sync_func: Callable = sync_all):
        self.db_path = db_path
        self.sync_func = sync_func
        self._thread = None
        self._cancel_event = None
        self._progress_q = None

    def sync(self, progress_q: queue.Queue, cancel_event: threading.Event) -> None:
        """Blocking sync operation writing progress messages into progress_q.

        Kept for tests that want to run sync inline. Prefer using
        start_async()/join()/cancel() in the view.
        """
        conn = create_connection(self.db_path)
        try:
            def enqueue(msg: str):
                try:
                    progress_q.put(msg)
                except Exception:
                    pass

            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM parts")
            before_parts = cur.fetchone()[0]

            try:
                # Ensure sync operations are wrapped in a transaction and
                # committed on success or rolled back on exception.
                with conn:
                    self.sync_func(conn, progress=enqueue, cancel_event=cancel_event)

                # Re-query counts after successful commit
                cur = conn.cursor()
                cur.execute("SELECT count(*) FROM parts")
                after_parts = cur.fetchone()[0]
                new_parts = max(0, after_parts - before_parts)
                # update SQLite query planner statistics and perform DB optimizations
                try:
                    enqueue("INFO: Running ANALYZE to update query planner statistics")
                    cur.execute("ANALYZE")
                except Exception:
                    # ANALYZE may not be available or could fail; log a message but don't abort
                    enqueue("WARN: ANALYZE failed or unsupported on this SQLite build")

                enqueue(f"SUMMARY: Sync complete — {new_parts} new parts added")
            except SyncCancelled:
                enqueue("SUMMARY: Sync cancelled")
            except Exception as exc:
                enqueue(f"ERROR: {exc}")
                enqueue(f"SUMMARY: Sync failed — {exc}")
                raise
            finally:
                enqueue("ALL_DONE")
        finally:
            conn.close()

    # --- Async control API for the view to offload threading responsibilities ---
    def start_async(self) -> queue.Queue:
        """Start sync in a background thread and return the progress queue.

        The view should hold onto the returned queue and construct a dialog
        to display messages from it. Use cancel() to request cancellation and
        join() to wait for completion.
        """
        if self._thread and self._thread.is_alive():
            raise RuntimeError("Sync already running")
        self._progress_q = queue.Queue()
        self._cancel_event = threading.Event()
        self._thread = threading.Thread(target=self._run_sync, args=(self._progress_q, self._cancel_event), daemon=True)
        self._thread.start()
        return self._progress_q

    def _run_sync(self, progress_q: queue.Queue, cancel_event: threading.Event):
        try:
            self.sync(progress_q, cancel_event)
        finally:
            # ensure ALL_DONE is present even if sync() raised before enqueueing
            try:
                progress_q.put("ALL_DONE")
            except Exception:
                pass

    def cancel(self):
        if self._cancel_event:
            self._cancel_event.set()

    def join(self, timeout: float = None):
        if self._thread:
            self._thread.join(timeout)
            if not (self._thread and self._thread.is_alive()):
                self._thread = None
        # clear progress queue reference — consumers should have drained it
        q = self._progress_q
        self._progress_q = None
        self._cancel_event = None
        return q

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    @property
    def progress_queue(self) -> queue.Queue:
        return self._progress_q
