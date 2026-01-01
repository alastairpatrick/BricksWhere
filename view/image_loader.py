import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def fetch_image_bytes(db_path: str, url: str) -> Optional[bytes]:
    """Fetch image bytes for `url` using requests-cache with sqlite backend.

    If `url` is a local path or file:// URL, load directly from disk. Return
    bytes on success or None on failure.
    """
    # local file handling
    if not url:
        return None
    if url.startswith("file://"):
        path = url[7:]
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
        return None
    if os.path.exists(url):
        with open(url, "rb") as f:
            return f.read()

    # attempt HTTP fetch using requests-cache; fall back to requests if not available
    try:
        import requests_cache
    except Exception:
        import requests
        try:
            logger.debug("fetching via requests %s", url)
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            return r.content
        except Exception as e:
            logger.debug("requests fetch failed: %s", e)
            return None

    try:
        # use the application sqlite DB as the cache backing store per design
        sess = requests_cache.CachedSession(cache_name=db_path, backend='sqlite')
        logger.debug("fetching via requests-cache %s with cache %s", url, db_path)
        r = sess.get(url, timeout=5)
        r.raise_for_status()
        return r.content
    except Exception:
        import traceback
        logger.debug("requests-cache fetch failed for %s: %s", url, traceback.format_exc())
        return None


class BackgroundImageFetcher:
    """Fetch images for a list of element dicts in a background thread.

    Usage:
        fetcher = BackgroundImageFetcher(db_path)
        q = fetcher.start(elements)
        # read (color, bytes) tuples from q until 'ALL_DONE'
        fetcher.cancel()  # to request cancellation
        fetcher.join()
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._thread = None
        self._cancel = None
        self._q = None

    def start(self, images: list):
        import queue, threading

        if self._thread and self._thread.is_alive():
            raise RuntimeError("Already running")
        self._q = queue.Queue()
        self._cancel = threading.Event()
        logger.debug("BackgroundImageFetcher.start creating thread for %d images", len(images))
        self._thread = threading.Thread(target=self._run, args=(images, self._q, self._cancel), daemon=True)
        self._thread.start()
        return self._q

    def _run(self, images, q, cancel_event):
        logger.debug("BackgroundImageFetcher._run entered")
        for image in images:
            if cancel_event.is_set():
                break
            url = image.get("img_url")
            tag = image.get("tag")
            try:
                logger.debug("BackgroundImageFetcher fetching %s", url)
                b = fetch_image_bytes(self.db_path, url)
                logger.debug("BackgroundImageFetcher fetched bytes=%s for %s", None if b is None else len(b), url)
                q.put((tag, b))
            except Exception:
                logger.exception("BackgroundImageFetcher exception fetching %s", url)
                q.put((tag, None))
        q.put("ALL_DONE")

    def cancel(self):
        if self._cancel:
            self._cancel.set()

    def join(self, timeout: float = None):
        if self._thread:
            self._thread.join(timeout)
            self._thread = None
        q = self._q
        self._q = None
        self._cancel = None
        return q
