import queue


class SyncProgressViewModel:
    """Process progress messages and expose a simple state for the view.

    The view-model collects textual entries, a numerical progress value (0-100),
    and a `ready_to_close` flag which is set once an ALL_DONE message is observed.
    """
    def __init__(self, total_steps: int = 12):
        self.entries = []
        self.progress = 0
        self.ready_to_close = False
        self.total_steps = max(1, total_steps)

    def process_msg(self, msg: str):
        if msg == "ALL_DONE":
            self.ready_to_close = True
            return
        self.entries.append(msg)
        self.progress = min(100, int(len(self.entries) * 100 / self.total_steps))

    def process_queue(self, q: queue.Queue):
        while self.process_queue_once(q) is not None:
            pass

    def process_queue_once(self, q: queue.Queue):
        """Consume at most one message from the queue and process it.

        Returns the processed message or None if queue empty.
        """
        try:
            msg = q.get_nowait()
        except queue.Empty:
            return None
        if msg == "ALL_DONE":
            self.ready_to_close = True
            return msg
        self.process_msg(msg)
        return msg
