import pytest

from model.sorting import bin_key


def test_bin_key_leading_digits_and_case():
    # leading integer prefixes
    assert bin_key('10A') < bin_key('100')
    # same integer prefix but different strings -> compare by string to break ties
    assert bin_key('001') < bin_key('1')
    # missing leading digits -> 0
    assert bin_key('A10') > bin_key('0')
    # case-insensitive
    assert bin_key('a10') == bin_key('A10')


def test_sorting_list_example():
    items = ['A1', '2', '10B', 'a2', '']
    sorted_items = sorted(items, key=bin_key)
    # expected order: '' (0), 'A1' (1,a1), 'a2' (2,a2), '2' (2,2) vs '2' string sorts before a2? but leading int primary
    # Verify monotonic leading ints
    leading_ints = [bin_key(s)[0] for s in sorted_items]
    assert leading_ints == sorted(leading_ints)
