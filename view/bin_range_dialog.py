from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox, QWidget



class BinRangeDialog(QDialog):
    """Dialog prompting for a start and end bin number and an "Include Images" option.

    Generate is disabled until both fields are non-empty and the end value
    sorts after the start value (ascending string order).
    """

    def __init__(self, parent=None, executor=None, viewmodel=None):
        super().__init__(parent)
        self.setWindowTitle("Bin Range")
        # allow injecting a viewmodel for tests; defer creating a default
        # viewmodel until generation to avoid creating BackgroundTask timers
        # during dialog construction.
        if viewmodel is None:
            from viewmodel.bin_range_viewmodel import BinRangeViewModel
            self._vm = BinRangeViewModel(executor=executor)
        else:
            self._vm = viewmodel
        self._build()

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
        self._include_images.setChecked(False)
        v.addWidget(self._include_images)

        # PDF viewer placed between checkbox and buttons
        self._viewer = PdfViewer(self)
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

        def on_completed(future):
            try:
                data = future.result()
                self._viewer.set_data(data)
            finally:
                self._generate.setEnabled(True)
                self._cancel.setEnabled(True)

        # connect and remember handler so we can disconnect on close
        self._vm.background_task.completed.connect(on_completed)
        # trigger generation
        self._vm.generate_pdf(start, end, include)


class PdfViewer(QWidget):
    """Simple PDF viewer wrapper.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc = QPdfDocument(self)
        self._view = QPdfView(self)
        l = QVBoxLayout(self)
        l.addWidget(self._view)
        self._view.setDocument(self._doc)

    def set_data(self, data: bytes):
        ba = QByteArray(data)
        buf = QBuffer(ba)
        buf.open(QIODevice.ReadOnly)
        self._doc.load(buf)

