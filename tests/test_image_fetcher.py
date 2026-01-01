import os
import tempfile
import queue
from view.image_loader import BackgroundImageFetcher


SINGLE_PIXEL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_background_image_fetcher_reads_local_files(tmp_path):
    # create two small png files
    p1 = tmp_path / "a.png"
    p2 = tmp_path / "b.png"
    p1.write_bytes(SINGLE_PIXEL_PNG)
    p2.write_bytes(SINGLE_PIXEL_PNG)

    elements = [
        {"color": "Red", "img_url": str(p1)},
        {"color": "Blue", "img_url": str(p2)},
    ]

    fetcher = BackgroundImageFetcher(db_path=":memory:")
    q = fetcher.start(elements)

    seen = {}
    # collect until ALL_DONE
    while True:
        item = q.get(timeout=2)
        if item == "ALL_DONE":
            break
        color, data = item
        seen[color] = data

    # ensure both colors were fetched and bytes match
    assert set(seen.keys()) == {"Red", "Blue"}
    for b in seen.values():
        assert b == SINGLE_PIXEL_PNG

    fetcher.join()
