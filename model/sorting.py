"""Sorting helpers for bin/set/part identifiers.

Expose a `int_prefixed_key` function that returns a tuple suitable for ordering such
that values are ordered primarily by the integer prefix (leading digits),
falling back to case-insensitive string comparison to break ties.
"""
from typing import Tuple


def _leading_int(s: str) -> int:
    if s is None:
        return 0
    s = str(s)
    i = 0
    digits = []
    while i < len(s) and s[i].isdigit():
        digits.append(s[i])
        i += 1
    if not digits:
        return 0
    try:
        return int(''.join(digits))
    except Exception:
        return 0


def int_prefixed_key(s: str) -> Tuple[int, str]:
    """Return a sort key for bin/set/part identifiers.

    The key is (leading_integer_prefix, lowercased_string). Leading digits are
    treated as a decimal integer; missing leading digits yield 0.
    """
    return (_leading_int(s), str(s or '').lower())
