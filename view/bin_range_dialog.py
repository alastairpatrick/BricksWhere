from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox, QWidget

from viewmodel.bin_range_viewmodel import BinRangeViewModel


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

        self._build()

    def closeEvent(self, event):
        # disconnect from background task to avoid handling events after close
        self._vm.background_task.completed.disconnect(self.on_generate_completed)
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

        btns = QHBoxLayout()
        btns.addStretch()
        self._cancel = QPushButton("Cancel")
        self._generate = QPushButton("Generate")
        self._generate.setEnabled(False)
        btns.addWidget(self._cancel)
        btns.addWidget(self._generate)
        v.addLayout(btns)

        # connections
        self._start.textChanged.connect(self._update_generate_state)
        self._end.textChanged.connect(self._update_generate_state)
        self._cancel.clicked.connect(self.reject)
        # wire generate to trigger viewmodel pdf generation
        self._generate.clicked.connect(self._on_generate)

    def _update_generate_state(self, _text=None):
        s = (self._start.text() or "").strip()
        e = (self._end.text() or "").strip()
        if not s or not e:
            self._generate.setEnabled(False)
            return
        # enable only if end sorts after start (ascending order)
        self._generate.setEnabled(e > s)

    @property
    def include_images(self):
        return self._include_images.isChecked()

    def _on_generate(self):
        # disable controls while generating
        self._generate.setEnabled(False)
        self._cancel.setEnabled(False)

        start = (self._start.text() or "").strip()
        end = (self._end.text() or "").strip()
        include = self.include_images

        # trigger generation
        self._vm.generate_pdf(start, end, include)

    def on_generate_completed(self, future):
        try:
            data = future.result()
            self._viewer.set_data(data)
        finally:
            self._generate.setEnabled(True)
            self._cancel.setEnabled(True)
