import time
from typing import Optional
from concurrent.futures import Future

from viewmodel.background_task import BackgroundTask


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
            # simple hard-coded minimal PDF bytes containing "Hello World"
            pdf = _make_hello_pdf_bytes()
            return pdf

        return self.background_task.run(worker)


def _make_hello_pdf_bytes() -> bytes:
    # Build a minimal PDF programmatically with correct offsets
    parts = []
    offsets = []

    def add(s: bytes):
        offsets.append(len(b"".join(parts)))
        parts.append(s)

    header = b"%PDF-1.4\n%\xFF\xFF\xFF\xFF\n"
    add(header)

    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    add(obj1)

    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    add(obj2)

    obj3 = b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    add(obj3)

    stream = b"BT /F1 24 Tf 72 720 Td (Hello World) Tj ET"
    obj4_stream = b"4 0 obj\n<< /Length %d >>\nstream\n" % (len(stream),)
    add(obj4_stream)
    add(stream + b"\n")
    obj4_end = b"endstream\nendobj\n"
    add(obj4_end)

    obj5 = b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    add(obj5)

    # xref
    xref_start = len(b"".join(parts))
    xref = [b"xref\n0 6\n0000000000 65535 f \n"]
    for off in offsets:
        xref.append(b"%010d 00000 n \n" % (off,))
    xref_bytes = b"".join(xref)
    parts.append(xref_bytes)

    trailer = b"trailer\n<< /Root 1 0 R /Size 6 >>\nstartxref\n%d\n%%EOF\n" % (xref_start,)
    parts.append(trailer)

    return b"".join(parts)
