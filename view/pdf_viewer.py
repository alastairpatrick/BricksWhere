from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QVBoxLayout, QWidget


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