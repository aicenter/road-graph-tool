import time
from unittest import mock

import pytest

from roadgraphtool.exceptions import OverpassRequestError
from roadgraphtool.overpass_client import (
    OverpassPolicyConfig,
    build_headers,
    query_json,
)


def _failing_api(error, status=None):
    api = mock.Mock()
    api.endpoint = "https://overpass.example/api/interpreter"
    api._status = status
    api.timeout = 25
    api.slot_available_countdown = 0
    api.get = mock.Mock(side_effect=error)
    return api


def test_query_json_explains_502():
    import overpass

    original = overpass.UnknownOverpassError("The request returned status code 502")
    api = _failing_api(original, status=502)

    with pytest.raises(OverpassRequestError, match=r"overloaded or temporarily unavailable \(HTTP 502\)") as info:
        query_json(api, "[out:json];node(1);out;")

    assert "https://overpass.example/api/interpreter" in str(info.value)
    assert "overpass.endpoint" in str(info.value)
    assert info.value.__cause__ is original
    assert api.get.call_count == 1  # not retried


def test_query_json_explains_429_after_retries():
    import overpass

    api = _failing_api(overpass.MultipleRequestsError(), status=429)

    with mock.patch.object(time, "sleep"):
        with pytest.raises(OverpassRequestError, match=r"HTTP 429\) \(3 attempts\)") as info:
            query_json(api, "[out:json];node(1);out;", max_retries=2, retry_backoff_s=0.0)

    assert isinstance(info.value.__cause__, overpass.MultipleRequestsError)
    assert api.get.call_count == 3


def test_query_json_explains_runtime_error():
    import overpass

    api = _failing_api(overpass.ServerRuntimeError("runtime error: Query run out of memory"), status=200)

    with pytest.raises(OverpassRequestError, match="out of memory") as info:
        query_json(api, "[out:json];node(1);out;")

    assert "osm_file" in str(info.value)


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

