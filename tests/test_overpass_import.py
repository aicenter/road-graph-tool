from types import SimpleNamespace

from roadgraphtool.overpass_import import _configured_tag_keys, _tag_rows


def test_configured_tag_keys_defaults_to_empty():
    config = SimpleNamespace()

    assert _configured_tag_keys(config) == []


def test_configured_tag_keys_normalizes_and_deduplicates():
    config = SimpleNamespace(
        road_import=SimpleNamespace(tags=["highway", "name", "highway", None, ""])
    )

    assert _configured_tag_keys(config) == ["highway", "name"]


def test_tag_rows_keeps_configured_tags_for_inserted_elements_only():
    elements = [
        {"id": 1, "tags": {"highway": "residential", "name": "Main St", "surface": "asphalt"}},
        {"id": 2, "tags": {"highway": "service"}},
        {"id": 3, "tags": {"name": "Skipped"}},
    ]

    rows = _tag_rows(
        elements,
        "way_id",
        {"highway": 10, "name": 11},
        allowed_ids={1, 3},
    )

    assert rows == [
        {"way_id": 1, "tag_id": 10, "tag_value": "residential"},
        {"way_id": 1, "tag_id": 11, "tag_value": "Main St"},
        {"way_id": 3, "tag_id": 11, "tag_value": "Skipped"},
    ]
