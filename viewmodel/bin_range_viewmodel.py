
import time
import io
from typing import Optional
from concurrent.futures import Future

from viewmodel.background_task import BackgroundTask

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


class BinRangeViewModel:
    def __init__(self, executor, name: str = "Bin Range Report", delay: float = 1.0):
        # executor may be a FakeExecutor in tests
        self.background_task = BackgroundTask(executor, name=name)
        self._delay = delay

    def generate_pdf(self, start: str, end: str, include_images: bool) -> Future:
        """Start background generation of a PDF and return a Future.

        The Future's result() will be the PDF bytes.
        """
        def worker(progress, is_cancelled):
            # simulate progress
            progress("Starting report generation")
            # delay to simulate work (can be 0 in tests)
            if self._delay and self._delay > 0:
                time.sleep(self._delay)
            progress("Assembling PDF bytes")
            # generate PDF bytes using ReportLab
            pdf = _make_hello_pdf_bytes()
            return pdf

        return self.background_task.run(worker)


def _make_hello_pdf_bytes() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica", 24)
    # place "Hello, World" near the top-left with some margin
    c.drawString(72, 720, "Hello, World")
    c.showPage()
    c.save()
    return buf.getvalue()
