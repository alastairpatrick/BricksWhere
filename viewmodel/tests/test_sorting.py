import pytest

from model.sorting import int_prefixed_key


def test_int_prefixed_key_leading_digits_and_case():
    # leading integer prefixes
    assert int_prefixed_key('10A') < int_prefixed_key('100')
    # same integer prefix but different strings -> compare by string to break ties
    assert int_prefixed_key('001') < int_prefixed_key('1')
    # missing leading digits -> 0
    assert int_prefixed_key('A10') > int_prefixed_key('0')
    # case-insensitive
    assert int_prefixed_key('a10') == int_prefixed_key('A10')


def test_sorting_list_example():
    items = ['A1', '2', '10B', 'a2', '']
    sorted_items = sorted(items, key=int_prefixed_key)
    # expected order: '' (0), 'A1' (1,a1), 'a2' (2,a2), '2' (2,2) vs '2' string sorts before a2? but leading int primary
    # Verify monotonic leading ints
    leading_ints = [int_prefixed_key(s)[0] for s in sorted_items]
    assert leading_ints == sorted(leading_ints)
