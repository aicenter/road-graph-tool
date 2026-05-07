import time
from unittest import mock

import pytest

from roadgraphtool.overpass_client import (
    OverpassPolicyConfig,
    build_headers,
    query_json,
)


def test_build_headers_requires_user_agent():
    with pytest.raises(ValueError):
        build_headers(OverpassPolicyConfig(user_agent=None))


def test_build_headers_includes_optional_fields():
    headers = build_headers(
        OverpassPolicyConfig(
            user_agent="my-tool/1.2 (contact: me@example.com)",
            from_email="me@example.com",
            referer="https://example.com/app",
        )
    )
    assert headers["User-Agent"].startswith("my-tool/1.2")
    assert headers["From"] == "me@example.com"
    assert headers["Referer"] == "https://example.com/app"


def test_query_json_retries_on_429():
    import overpass

    api = mock.Mock()
    api.slot_available_countdown = 2
    api.get = mock.Mock(
        side_effect=[
            overpass.MultipleRequestsError(),
            {"elements": [{"type": "node", "id": 1, "lat": 0.0, "lon": 0.0}]},
        ]
    )

    with mock.patch.object(time, "sleep") as sleep_mock:
        out = query_json(
            api,
            "[out:json];node(1);out;",
            build=False,
            max_retries=3,
            retry_backoff_s=0.1,
            retry_max_sleep_s=10.0,
        )

    assert "elements" in out
    assert api.get.call_count == 2
    assert sleep_mock.called

