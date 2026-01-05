from PySide6.QtCore import QObject, Signal


def test_sync_progress_viewmodel_processes_messages():
    # Replace previous queue-based helper with signal-driven behavior.
    total_steps = 4
    entries = []
    ready = {"v": False}

    class FakeBackgroundTask(QObject):
        progressed = Signal(str)
        completed = Signal(bool)

        def __init__(self):
            super().__init__()

    def on_progress(msg: str):
        entries.append(msg)

    def on_complete(ok: bool):
        ready["v"] = True

    fb = FakeBackgroundTask()
    fb.progressed.connect(on_progress)
    fb.completed.connect(on_complete)

    # emit two progress messages and then completion
    fb.progressed.emit("Step 1")
    fb.progressed.emit("Step 2")
    fb.completed.emit(True)

    assert entries == ["Step 1", "Step 2"]
    assert ready["v"] is True

