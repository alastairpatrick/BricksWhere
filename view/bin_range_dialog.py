import logging
from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox, QWidget, QFileDialog

from viewmodel.bin_range_viewmodel import BinRangeViewModel

logger = logging.getLogger(__name__)

class PdfViewer(QWidget):
    """Simple PDF viewer wrapper.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc = QPdfDocument(self)
        self._view = QPdfView(self)
        self._view.setPageMode(QPdfView.PageMode.MultiPage)
        self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        l = QVBoxLayout(self)
        l.addWidget(self._view)
        self._view.setDocument(self._doc)

    def set_data(self, data: bytes):
        ba = QByteArray(data)
        # keep buffer reachable in case document accesses it after set_data returns
        self._qbuffer = QBuffer(ba)
        self._qbuffer.open(QIODevice.ReadOnly)
        self._doc.load(self._qbuffer)


class BinRangeDialog(QDialog):
    """Dialog prompting for a start and end bin number and an "Include Images" option.

    Generate is disabled until both fields are non-empty and the end value
    sorts after the start value (ascending string order).
    """

    def __init__(self, parent=None,
                 executor=None,
                 viewmodel=None,
                 requests_session=None,
                 pdf_viewer_cls=PdfViewer):
        super().__init__(parent)
        self._pdf_viewer_cls = pdf_viewer_cls

        self.setWindowTitle("Bin Range")

        self._vm = viewmodel if viewmodel is not None else BinRangeViewModel(executor=executor, requests_session=requests_session)

        self._vm.background_task.completed.connect(self.on_generate_completed)
        self._vm.background_task.progressed.connect(self._on_progress)

        self._build()

    def closeEvent(self, event):
        # disconnect from background task to avoid handling events after close
        self._vm.background_task.completed.disconnect(self.on_generate_completed)
        self._vm.background_task.progressed.disconnect(self._on_progress)
        self._vm.background_task.shutdown()
        event.accept()

    def _build(self):
        v = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel("Start Bin Number:"))
        self._start = QLineEdit()
        row.addWidget(self._start)
        v.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("End Bin Number:"))
        self._end = QLineEdit()
        row2.addWidget(self._end)
        v.addLayout(row2)

        self._include_images = QCheckBox("Include Images")
        self._include_images.setChecked(True)
        v.addWidget(self._include_images)

        # PDF viewer placed between checkbox and buttons
        self._viewer = self._pdf_viewer_cls(self)
        v.addWidget(self._viewer)

        # status label for progress messages
        self._status = QLabel("")
        v.addWidget(self._status)

        btns = QHBoxLayout()
        btns.addStretch()
        self._close = QPushButton("Close")
        self._save = QPushButton("Save...")
        self._save.setEnabled(False)
        self._generate = QPushButton("Generate")
        self._generate.setEnabled(False)
        btns.addWidget(self._close)
        btns.addWidget(self._save)
        btns.addWidget(self._generate)
        v.addLayout(btns)

        # save handler
        self._save.clicked.connect(self._on_save)

        # connections
        self._start.textChanged.connect(self._update_generate_state)
        self._end.textChanged.connect(self._update_generate_state)
        self._close.clicked.connect(self.close)
        # wire generate to trigger viewmodel pdf generation
        self._generate.clicked.connect(self._on_generate)

        self._update_generate_state()
        
    def _on_progress(self, msg: str):
        # update status label with latest progress
        self._status.setText(msg)

    def _update_generate_state(self, _text=None):
        s = (self._start.text() or "").strip()
        e = (self._end.text() or "").strip()
        self._generate.setEnabled(not s or not e or e > s)

    @property
    def include_images(self):
        return self._include_images.isChecked()

    def _on_generate(self):
        # disable controls while generating
        self._generate.setEnabled(False)
        self._save.setEnabled(False)

        start = (self._start.text() or "").strip()
        end = (self._end.text() or "").strip()
        include = self.include_images

        # trigger generation
        self._vm.generate_pdf(start if start != "" else None, end if end != "" else None, include)

    def on_generate_completed(self, future):
        try:
            data = future.result()
            self._viewer.set_data(data)
            self._status.setText("")
            # remember last generated bytes and enable Save
            self._last_pdf = data
            self._save.setEnabled(bool(data))
        except Exception as e:
            self._status.setText("Error generating PDF.")
            logger.exception("Error generating PDF: %s", e)
        finally:
            self._generate.setEnabled(True)

    def _on_save(self):
        # show save dialog and write last generated PDF bytes
        data = getattr(self, '_last_pdf', None)
        if not data:
            return
        fname, _ = QFileDialog.getSaveFileName(self, "Save PDF", "bin-range.pdf", "PDF Files (*.pdf)")
        if not fname:
            return
        with open(fname, 'wb') as f:
            f.write(data)
