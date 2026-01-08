
import time
import io
import logging
from typing import Optional
from concurrent.futures import Future

from viewmodel.background_task import BackgroundTask
from model.db import create_connection

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
import requests

logger = logging.getLogger(__name__)

class BinRangeViewModel:
    def __init__(self, executor, db_path: str = "data.db", name: str = "Bin Range Report", delay: float = 1.0, requests_session=None):
        # executor may be a FakeExecutor in tests
        self.background_task = BackgroundTask(executor, name=name)
        self._delay = delay
        self.db_path = db_path
        self.requests_session = requests_session

    def generate_pdf(self, start: str, end: str, include_images: bool) -> Future:
        """Start background generation of a PDF and return a Future.

        The Future's result() will be the PDF bytes.
        """
        def worker(progress, is_cancelled):
            progress("Starting report generation")
            # optional artificial delay for tests
            if self._delay and self._delay > 0:
                time.sleep(self._delay)
            progress("Querying owned parts")
            rows = _fetch_owned_parts(self.db_path, start, end)
            progress(f"Rendering {len(rows)} rows to PDF")
            pdf = _render_bin_range_pdf(rows, start, end, include_images, requests_session=self.requests_session, progress=progress, is_cancelled=is_cancelled)
            return pdf

        return self.background_task.run(worker)


def _fetch_owned_parts(db_path: str, start: str, end: str):
    """Return a list of tuples (bin_num, part_num, part_name, quantity).

    Ownership is computed by joining user_sets -> inventories -> inventory_parts
    and multiplying inventory_part.quantity by user_sets.quantity. The user's
    explicit `user_part_bins` assignment is used when present; otherwise the
    implicit bin is the `part_num` itself.
    """
    sql = (
        "SELECT COALESCE(upb.bin_num, ip.part_num) AS bin_num, ip.part_num, COALESCE(p.name, ''), "
        "SUM(ip.quantity * us.quantity) as qty, ip.img_url "
        "FROM user_sets us "
        "JOIN inventories i ON i.set_num = us.set_num "
        "JOIN inventory_parts ip ON ip.inventory_id = i.id "
        "LEFT JOIN user_part_bins upb ON upb.part_num = ip.part_num "
        "LEFT JOIN parts p ON p.part_num = ip.part_num "
        "GROUP BY bin_num, ip.part_num, p.name "
    )
    with create_connection(db_path) as conn, conn:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()

    # Use shared sorting helper so the same ordering is used across the app.
    from model.sorting import bin_key

    start_key = bin_key(start)
    end_key = bin_key(end)

    # Filter rows in Python according to the same ordering semantics.
    filtered = [r for r in rows if start_key <= bin_key(r[0]) <= end_key]

    # Finally sort the filtered rows deterministically for the report.
    filtered.sort(key=lambda r: (bin_key(r[0]), str(r[1] or '')))
    return filtered


def _render_bin_range_pdf(rows, start: str, end: str, include_images: bool, requests_session=None, progress=None, is_cancelled=None) -> bytes:
    """Render the rows to a multi-page PDF (US Letter), repeating headers and
    adding page numbers. Returns PDF bytes. If `include_images` is True, try to
    download an image for each row using `requests_session` (if provided) or
    `requests` otherwise, and place it in the rightmost column.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)

    styles = getSampleStyleSheet()
    story = []

    title = Paragraph(f"Bin Range Report: {start} - {end}", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))

    # table header
    if include_images:
        data = [["Bin", "Part #", "Part Name", "Quantity", "Image"]]
    else:
        data = [["Bin", "Part #", "Part Name", "Quantity"]]

    # Prepare image download helper
    def _download_image(url, part_num=None):
        if not url:
            return None
        if progress:
            progress(f"Downloading image for {part_num or ''}")
        try:
            sess = requests_session or requests
            # requests_cache CachedSession implements .get
            resp = sess.get(url, timeout=5)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            logger.error("Failed to download image %s: %s", url, e)
            return None

    for r in rows:
        # r: (bin_num, part_num, part_name, qty, img_url)
        bin_val = str(r[0] or '')
        part_num = str(r[1] or '')
        part_name = str(r[2] or '')
        qty = str(r[3] or '')
        if include_images:
            img_url = r[4] if len(r) > 4 else None
            # abort if cancelled
            if is_cancelled and is_cancelled():
                if progress:
                    progress("Generation cancelled")
                return b""
            img_bytes = _download_image(img_url, part_num)
            if img_bytes:
                try:
                    img_buf = io.BytesIO(img_bytes)
                    img = RLImage(img_buf, width=40, height=40)
                except Exception:
                    img = ''
            else:
                img = ''
            data.append([bin_val, part_num, part_name, qty, img])
        else:
            data.append([bin_val, part_num, part_name, qty])

    # create table; let it split across pages and repeat the first row
    if include_images:
        table = Table(data, repeatRows=1, colWidths=[70, 110, 260, 50, 60])
    else:
        table = Table(data, repeatRows=1, colWidths=[80, 120, 260, 60])
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
    ]))

    story.append(table)

    def _add_page_number(canvas, doc):
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        width, height = letter
        canvas.drawCentredString(width / 2.0, 18, text)
        canvas.restoreState()

    doc.build(story, onFirstPage=_add_page_number, onLaterPages=_add_page_number)
    return buf.getvalue()
