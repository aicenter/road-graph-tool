from __future__ import annotations

import hashlib
import json
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import overpass

from roadgraphtool.exceptions import OverpassRequestError


@dataclass(frozen=True)
class OverpassPolicyConfig:
    endpoint: str = "https://overpass-api.de/api/interpreter"
    timeout_s: int | float = 25
    status_url: str | None = None
    proxies: dict | None = None

    # Required by overpass-api.de policy for scripts
    user_agent: str | None = None

    # Optional but recommended
    from_email: str | None = None
    referer: str | None = None

    # Retry behavior (429/504)
    max_retries: int = 6
    retry_backoff_s: float = 1.0
    retry_max_sleep_s: float = 120.0


def _read_nested(obj: Any, path: str, default: Any = None) -> Any:
    """
    Read nested values from dicts or SimpleNamespace-like objects.
    Path syntax: "a.b.c".
    """
    cur: Any = obj
    for part in path.split("."):
        if cur is None:
            return default
        if isinstance(cur, Mapping):
            cur = cur.get(part, default)
        else:
            cur = getattr(cur, part, default)
    return cur


def policy_config_from_config(config: Any) -> OverpassPolicyConfig:
    """
    Create an OverpassPolicyConfig from the project's parsed config object.

    Expected optional config keys (under `overpass`):
    - endpoint, timeout_s, status_url, user_agent, from_email, referer,
      max_retries, retry_backoff_s, retry_max_sleep_s
    """
    return OverpassPolicyConfig(
        endpoint=_read_nested(config, "overpass.endpoint", OverpassPolicyConfig.endpoint),
        timeout_s=_read_nested(config, "overpass.timeout_s", OverpassPolicyConfig.timeout_s),
        status_url=_read_nested(config, "overpass.status_url", None),
        proxies=_read_nested(config, "overpass.proxies", None),
        user_agent=_read_nested(config, "overpass.user_agent", None),
        from_email=_read_nested(config, "overpass.from_email", None),
        referer=_read_nested(config, "overpass.referer", None),
        max_retries=int(_read_nested(config, "overpass.max_retries", OverpassPolicyConfig.max_retries)),
        retry_backoff_s=float(
            _read_nested(config, "overpass.retry_backoff_s", OverpassPolicyConfig.retry_backoff_s)
        ),
        retry_max_sleep_s=float(
            _read_nested(config, "overpass.retry_max_sleep_s", OverpassPolicyConfig.retry_max_sleep_s)
        ),
    )


def build_headers(policy: OverpassPolicyConfig) -> dict[str, str]:
    if not policy.user_agent or not str(policy.user_agent).strip():
        raise ValueError(
            "Overpass requests require a custom User-Agent identifying your script/app. "
            "Set `overpass.user_agent` in the config."
        )

    headers: dict[str, str] = {
        # keep overpass lib default accept-charset behavior, but be explicit here too
        "Accept-Charset": "utf-8;q=0.7,*;q=0.7",
        "User-Agent": str(policy.user_agent).strip(),
    }
    if policy.from_email:
        headers["From"] = str(policy.from_email).strip()
    if policy.referer:
        headers["Referer"] = str(policy.referer).strip()
    return headers


def create_api(policy: OverpassPolicyConfig) -> overpass.API:
    # overpass 0.8.x: overpass.API exists but is deprecated; avoid warning spam in tests/logs
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            category=DeprecationWarning,
            message=r"overpass\.API is deprecated.*",
        )
        api = overpass.API(
            endpoint=policy.endpoint,
            timeout=policy.timeout_s,
            headers=build_headers(policy),
            proxies=policy.proxies,
            status_url=policy.status_url,
        )
    return api


_TRY_LATER_HINT = (
    "This is a problem of the server, not of the query. Run again later, or set `overpass.endpoint` to a less "
    "loaded Overpass instance."
)


def describe_overpass_error(api: Any, error: Exception, query: str, *, attempts: int) -> str:
    """Human-readable explanation of a failed Overpass request.

    The ``overpass`` library keeps only the HTTP status (``api._status``), not the response body.
    """
    endpoint = getattr(api, "endpoint", "the Overpass server")
    status = getattr(api, "_status", None)
    tries = f" ({attempts} attempts)" if attempts > 1 else ""

    if isinstance(error, overpass.MultipleRequestsError):
        reason = f"the server kept refusing the request as too many requests (HTTP 429){tries}."
        hint = "Another query from this IP address may still be running. Wait a few minutes and run again."
    elif isinstance(error, overpass.ServerLoadError):
        reason = f"the server kept timing out because of high load (HTTP 504){tries}."
        hint = _TRY_LATER_HINT
    elif isinstance(error, overpass.TimeoutError):
        reason = f"no response within the client timeout of {getattr(api, 'timeout', '?')} s."
        hint = "Increase `overpass.timeout_s`, or run again when the server is less loaded."
    elif isinstance(error, overpass.OverpassSyntaxError):
        reason = "the server rejected the query as invalid (HTTP 400)."
        hint = f"This is a bug in the generated query:\n{query.strip()[:1000]}"
    elif isinstance(error, overpass.ServerRuntimeError):
        reason = f"the server aborted the query: {error}."
        hint = (
            "The query result is probably too large for the server (time or memory limit). Use a smaller area, "
            "or the `osm_file` source of `road_import` with a local OSM extract."
        )
    elif status in (502, 503):
        reason = (
            f"the server is overloaded or temporarily unavailable (HTTP {status}). Public Overpass instances "
            "reject requests when all their query slots are busy and their queue is full."
        )
        hint = _TRY_LATER_HINT
    else:
        reason = f"unexpected error{f' (HTTP {status})' if status else ''}: {error}."
        hint = ""

    return f"Overpass request to {endpoint} failed: {reason} {hint}".strip()


def query_json(
    api: overpass.API,
    query: str,
    *,
    build: bool = False,
    cache_dir: Path | None = None,
    refresh_cache: bool = False,
    max_retries: int = 6,
    retry_backoff_s: float = 1.0,
    retry_max_sleep_s: float = 120.0,
) -> dict[str, Any]:
    """
    Execute an Overpass query and return JSON (raw Overpass JSON, not GeoJSON).

    - If `build=False` (default), `query` must be a full Overpass QL program (may include
      `[out:json]`, `[timeout:...]`, and `out ...;`).
    - Retries on 429 (MultipleRequestsError) and 504 (ServerLoadError).
    - Any other failure, or a 429/504 persisting after *max_retries*, raises ``OverpassRequestError``
      describing the cause, with the original error chained.
    """
    cache_path: Path | None = None
    if cache_dir is not None:
        cache_key = hashlib.sha256(query.strip().encode("utf-8")).hexdigest()
        cache_path = Path(cache_dir) / "query_json" / f"{cache_key}.json"

        if not refresh_cache and cache_path.exists():
            with cache_path.open("r", encoding="utf-8") as f:
                return json.load(f)

    attempt = 0
    while True:
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"overpass\..*")
                result = api.get(query, responseformat="json", build=build)

            if cache_path is not None:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
                with tmp_path.open("w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False)
                tmp_path.replace(cache_path)

            return result
        except overpass.MultipleRequestsError as e:
            # Per Overpass docs/policy: respect reported wait time; API exposes /status parsing helpers.
            wait_s = getattr(api, "slot_available_countdown", 0) or 0
            wait_s = max(wait_s, 1)
            error = e
        except overpass.ServerLoadError as e:
            # Server suggests retrying later; we back off.
            wait_s = 0
            error = e
        except overpass.OverpassError as e:
            raise OverpassRequestError(describe_overpass_error(api, e, query, attempts=attempt + 1)) from e
        if attempt >= max_retries:
            raise OverpassRequestError(describe_overpass_error(api, error, query, attempts=attempt + 1)) from error

        backoff_s = retry_backoff_s * (2**attempt)
        sleep_s = min(max(wait_s, backoff_s), retry_max_sleep_s)
        time.sleep(sleep_s)
        attempt += 1


def query_json_from_config(config: Any, query: str, *, build: bool = False) -> dict[str, Any]:
    policy = policy_config_from_config(config)
    api = create_api(policy)

    export = getattr(config, "export", None)
    output_dir = None
    if export is not None and hasattr(export, "dir"):
        output_dir = Path(export.dir)
    elif hasattr(config, "output_dir"):
        output_dir = Path(getattr(config, "output_dir"))

    return query_json(
        api,
        query,
        build=build,
        cache_dir=output_dir,
        max_retries=policy.max_retries,
        retry_backoff_s=policy.retry_backoff_s,
        retry_max_sleep_s=policy.retry_max_sleep_s,
    )


def elements_by_type(overpass_json: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """
    Index Overpass JSON `elements` by element type (node/way/relation).
    """
    elements = overpass_json.get("elements", [])
    out: dict[str, list[dict[str, Any]]] = {"node": [], "way": [], "relation": []}
    for el in elements:
        t = el.get("type")
        if t in out:
            out[t].append(el)
    return out

