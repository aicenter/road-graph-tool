from types import SimpleNamespace

import pytest

from roadgraphtool.road_import import check_style_matches_profile, get_network_profile


def test_network_profile_defaults_to_car():
    assert get_network_profile(SimpleNamespace(road_import=SimpleNamespace())) == "car"
    assert get_network_profile(SimpleNamespace()) == "car"


def test_network_profile_pedestrian():
    config = SimpleNamespace(road_import=SimpleNamespace(profile="pedestrian"))

    assert get_network_profile(config) == "pedestrian"


def test_network_profile_unknown_raises():
    config = SimpleNamespace(road_import=SimpleNamespace(profile="bicycle"))

    with pytest.raises(ValueError, match="Unknown road_import.profile"):
        get_network_profile(config)


@pytest.mark.parametrize(
    "profile, style_file",
    [
        ("car", "pipeline"),
        ("pedestrian", "pedestrian"),
        ("car", "simple"),
        ("pedestrian", "custom/pipeline.lua"),
        ("car", "lua_styles/pedestrian.lua"),
    ],
)
def test_style_matches_profile_accepts(profile, style_file):
    check_style_matches_profile(profile, style_file)


@pytest.mark.parametrize("profile, style_file", [("pedestrian", "pipeline"), ("car", "pedestrian")])
def test_style_matches_profile_rejects_builtin_style_of_other_profile(profile, style_file):
    with pytest.raises(ValueError, match="built-in style"):
        check_style_matches_profile(profile, style_file)
