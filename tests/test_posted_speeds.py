from types import SimpleNamespace

import pytest

from roadgraphtool.posted_speeds import DEFAULT_POSTED_SPEEDS, get_posted_speeds


def _config(posted_speeds=None):
    contraction = SimpleNamespace(speed_source="posted")
    if posted_speeds is not None:
        contraction.posted_speeds = posted_speeds
    return SimpleNamespace(contraction=contraction)


def test_defaults_without_overrides():
    assert get_posted_speeds(_config()) == DEFAULT_POSTED_SPEEDS


def test_overrides_are_merged_into_defaults():
    posted_speeds = get_posted_speeds(
        _config(SimpleNamespace(default=30, highway=SimpleNamespace(residential=30, motorway=130)))
    )

    assert posted_speeds["default"] == 30
    assert posted_speeds["highway"]["residential"] == 30
    assert posted_speeds["highway"]["motorway"] == 130
    assert posted_speeds["highway"]["living_street"] == 20
    assert posted_speeds["zones"] == DEFAULT_POSTED_SPEEDS["zones"]


def test_overrides_do_not_change_the_built_in_defaults():
    get_posted_speeds(_config({"highway": {"motorway": 130}}))

    assert DEFAULT_POSTED_SPEEDS["highway"]["motorway"] == 80


def test_unknown_key_is_rejected():
    with pytest.raises(ValueError, match="unknown keys"):
        get_posted_speeds(_config({"defaults": 50}))


@pytest.mark.parametrize("speed", [0, -10, "50", True])
def test_speeds_must_be_positive_numbers(speed):
    with pytest.raises(ValueError, match="positive number"):
        get_posted_speeds(_config({"zones": {"CZ:urban": speed}}))
