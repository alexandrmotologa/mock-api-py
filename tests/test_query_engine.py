"""Unit tests for query engine filtering, search, sorting, and pagination."""

from mock_api_py.query_engine import execute_query


def test_exact_and_type_coercion(sample_data):
    items = sample_data["products"]

    # String match
    res = execute_query(items, {"category": "electronics"})
    assert len(res.items) == 2

    # Boolean coercion
    res_bool = execute_query(items, {"inStock": "true"})
    assert len(res_bool.items) == 2

    res_false = execute_query(items, {"inStock": "false"})
    assert len(res_false.items) == 1
    assert res_false.items[0]["id"] == 2


def test_comparative_operators(sample_data):
    items = sample_data["products"]

    # _gte
    res_gte = execute_query(items, {"price_gte": "89.99"})
    assert len(res_gte.items) == 2
    ids = {item["id"] for item in res_gte.items}
    assert ids == {2, 3}

    # _gt
    res_gt = execute_query(items, {"price_gt": "89.99"})
    assert len(res_gt.items) == 1
    assert res_gt.items[0]["id"] == 3

    # _lte
    res_lte = execute_query(items, {"price_lte": "50"})
    assert len(res_lte.items) == 1
    assert res_lte.items[0]["id"] == 1

    # _lt
    res_lt = execute_query(items, {"price_lt": "89.99"})
    assert len(res_lt.items) == 1
    assert res_lt.items[0]["id"] == 1

    # _ne
    res_ne = execute_query(items, {"price_ne": "29.99"})
    assert len(res_ne.items) == 2
    assert 1 not in [item["id"] for item in res_ne.items]

    # _like
    res_like = execute_query(items, {"title_like": "board"})
    assert len(res_like.items) == 1
    assert res_like.items[0]["title"] == "Mechanical Keyboard"


def test_full_text_search(sample_data):
    items = sample_data["products"]

    res = execute_query(items, {"q": "keyboard"})
    assert len(res.items) == 1
    assert res.items[0]["title"] == "Mechanical Keyboard"

    res_case = execute_query(items, {"q": "WIRELESS"})
    assert len(res_case.items) == 1
    assert res_case.items[0]["id"] == 1


def test_sorting(sample_data):
    items = sample_data["products"]

    # Ascending
    res_asc = execute_query(items, {"_sort": "price", "_order": "asc"})
    prices_asc = [i["price"] for i in res_asc.items]
    assert prices_asc == [29.99, 89.99, 199.99]

    # Descending
    res_desc = execute_query(items, {"_sort": "price", "_order": "desc"})
    prices_desc = [i["price"] for i in res_desc.items]
    assert prices_desc == [199.99, 89.99, 29.99]


def test_pagination(sample_data):
    items = sample_data["products"]

    # Page 1 of size 2
    res_p1 = execute_query(items, {"_page": "1", "_limit": "2"}, request_url="http://test/products")
    assert len(res_p1.items) == 2
    assert res_p1.total_count == 3
    assert res_p1.items[0]["id"] == 1
    assert res_p1.items[1]["id"] == 2
    assert res_p1.link_header is not None
    assert 'rel="next"' in res_p1.link_header
    assert 'rel="last"' in res_p1.link_header

    # Page 2 of size 2
    res_p2 = execute_query(items, {"_page": "2", "_limit": "2"}, request_url="http://test/products")
    assert len(res_p2.items) == 1
    assert res_p2.total_count == 3
    assert res_p2.items[0]["id"] == 3
    assert 'rel="prev"' in res_p2.link_header
    assert 'rel="first"' in res_p2.link_header
