import queue


def test_sync_progress_viewmodel_processes_messages():
    from viewmodel import SyncProgressViewModel

    vm = SyncProgressViewModel(total_steps=4)
    q = queue.Queue()
    q.put("Step 1")
    q.put("Step 2")
    q.put("ALL_DONE")
    vm.process_queue(q)
    assert vm.entries == ["Step 1", "Step 2"]
    assert vm.ready_to_close is True
    assert vm.progress == min(100, int(2 * 100 / 4))

