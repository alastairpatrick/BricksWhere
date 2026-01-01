from PySide6.QtWidgets import (
    QDialog,
    QPushButton,
    QListWidget,
    QProgressBar,
    QHBoxLayout,
    QVBoxLayout,
)
from PySide6.QtCore import Signal, QTimer

from viewmodel import SyncProgressViewModel


class SyncProgressDialog(QDialog):
    # emitted when dialog switches to OK and is ready to be closed (test hook)
    ready_to_close = Signal()

    def __init__(self, sync_vm, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Synchronizing with Rebrickable")
        self.setModal(True)
        self.resize(400, 300)
        self._sync_vm = sync_vm
        self._q = sync_vm.progress_queue

        self._list = QListWidget()
        self._progress = QProgressBar()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        self.closeEvent = lambda event: self._on_cancel()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self._cancel_btn)

        layout = QVBoxLayout()
        layout.addWidget(self._list)
        layout.addWidget(self._progress)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self._progress_vm = SyncProgressViewModel()
        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self.process_queue_once)
        self._timer.start()
        
    def _on_cancel(self):
        # request cancel from the view-model and update UI
        self._cancel_btn.setEnabled(False)
        try:
            self._sync_vm.cancel()
        except Exception:
            pass
        self._list.addItem("Cancellation requested; finishing current download and rolling back...")

    def _switch_to_ok(self):
        # replace the Cancel button with OK which closes the dialog
        try:
            self._cancel_btn.clicked.disconnect()
        except Exception:
            pass
        self._cancel_btn.setText("OK")
        self._cancel_btn.setEnabled(True)
        self._cancel_btn.clicked.connect(self.accept)
        # signal that dialog is ready to be closed (useful for tests)
        try:
            self.ready_to_close.emit()
        except Exception:
            pass

    def _poll(self):
        # let view-model process available messages
        self._progress_vm.process_queue(self._q)
        # refresh UI list from view-model state
        self._list.clear()
        for e in self._progress_vm.entries:
            self._list.addItem(e)

            # So user can see latest progress, auto-scroll if already at bottom
            scrollbar = self._list.verticalScrollBar()
            if scrollbar.value() == scrollbar.maximum():
                self._list.scrollToBottom()

        self._progress.setValue(self._progress_vm.progress)
        if self._progress_vm.ready_to_close:
            self._timer.stop()
            self._switch_to_ok()

    def process_queue_once(self):
        """Process any pending messages in the progress queue once.

        This is a public helper to allow deterministic unit tests to drive the
        queue processing without relying on QTimer.
        """
        # reuse internal logic implemented in _poll
        return self._poll()
