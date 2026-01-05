import logging
from PySide6.QtWidgets import (
    QDialog,
    QPushButton,
    QListWidget,
    QProgressBar,
    QHBoxLayout,
    QVBoxLayout,
)
from PySide6.QtCore import Signal

logger = logging.getLogger(__name__)


class SyncProgressDialog(QDialog):
    # emitted when dialog switches to OK and is ready to be closed (test hook)
    ready_to_close = Signal()

    def __init__(self, sync_vm, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Synchronizing with Rebrickable")
        self.setModal(True)
        self.resize(400, 300)
        self._sync_vm = sync_vm

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

        sync_vm.background_task.progressed.connect(self._on_progress)
        sync_vm.background_task.completed.connect(self._on_complete)
        
    def _on_cancel(self):
        # request cancel from the view-model and update UI
        self._cancel_btn.setEnabled(False)
        try:
            self._sync_vm.background_task.cancel()
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

    def _on_progress(self, msg: str):
        # append message to list and update progress bar
        self._list.addItem(msg)

        # So user can see latest progress, auto-scroll if already at bottom
        scrollbar = self._list.verticalScrollBar()
        if scrollbar.value() == scrollbar.maximum():
            self._list.scrollToBottom()

        current_count = self._list.count()
        total_count = 26  # assuming 26 total steps
        if current_count > total_count:
            logger.warning(
                "More progress messages (%d) than expected total (%d)", current_count, total_count
            )

        progress_pct = min(100, current_count * 100 / total_count)  # assuming 12 total steps
        self._progress.setValue(progress_pct)

    def _on_complete(self, success: bool):
        # switch Cancel button to OK
        self._switch_to_ok()
