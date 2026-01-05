import queue


class SyncProgressViewModel:
    """Lightweight helper retained for tests: process a queue of progress messages."""
    def __init__(self, total_steps: int = 10):
        self.entries = []
        self.progress = 0
        self.ready_to_close = False
        self.total_steps = total_steps

    def process_queue(self, q: 'queue.Queue'):
        items = []
        try:
            while True:
                item = q.get_nowait()
                if item == "ALL_DONE":
                    self.ready_to_close = True
                    continue
                items.append(item)
        except queue.Empty:
            pass
        self.entries = items
        self.progress = min(100, int(len(items) * 100 / max(1, self.total_steps)))
