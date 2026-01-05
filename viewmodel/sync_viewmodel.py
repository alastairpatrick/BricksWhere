from concurrent.futures import ThreadPoolExecutor

from model.db import connection_ctx
from model.rebrickable import SyncCancelled, sync_all
from viewmodel.background_task import BackgroundTask


class SyncViewModel:
    """Encapsulate synchronization logic so it can be tested.

    The view-model sends progress messages to a queue and obeys an external
    cancel_event. A custom sync_func may be injected for testing.
    """
    def __init__(self, db_path: str, executor: ThreadPoolExecutor):
        self.db_path = db_path
        self.background_task = BackgroundTask(executor)

    def start_sync(self, progress, is_cancelled) -> None:
        with connection_ctx(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM parts")
            before_parts = cur.fetchone()[0]

            try:
                sync_all(conn, None, progress=progress, is_cancelled=is_cancelled)

                # Re-query counts after successful commit
                cur = conn.cursor()
                cur.execute("SELECT count(*) FROM parts")
                after_parts = cur.fetchone()[0]
                new_parts = max(0, after_parts - before_parts)

                # update SQLite query planner statistics and perform DB optimizations
                try:
                    progress("INFO: Running ANALYZE to update query planner statistics")
                    cur.execute("ANALYZE")
                except Exception:
                    # ANALYZE may not be available or could fail; log a message but don't abort
                    progress("WARN: ANALYZE failed or unsupported on this SQLite build")

                progress(f"SUMMARY: Sync complete — {new_parts} new parts added")

            except SyncCancelled:
                progress("SUMMARY: Sync cancelled")

    def start_async(self) -> None:
        self.background_task.run(self.start_sync)

