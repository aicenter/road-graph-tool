from __future__ import annotations

import hashlib
import json
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import overpass


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
        except overpass.MultipleRequestsError:
            # Per Overpass docs/policy: respect reported wait time; API exposes /status parsing helpers.
            wait_s = getattr(api, "slot_available_countdown", 0) or 0
            wait_s = max(wait_s, 1)
        except overpass.ServerLoadError:
            # Server suggests retrying later; we back off.
            wait_s = 0
        if attempt >= max_retries:
            raise

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

