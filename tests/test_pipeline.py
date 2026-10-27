from types import SimpleNamespace

from roadgraphtool.pipeline import _is_activated


def test_step_is_activated_only_with_activated_true():
    config = SimpleNamespace(
        export=SimpleNamespace(activated=True),
        dm_generator=SimpleNamespace(activated=False),
        # a section only with credentials merged from the secrets file
        viewer_deploy=SimpleNamespace(password="secret"),
    )

    assert _is_activated(config, "export")
    assert not _is_activated(config, "dm_generator")
    assert not _is_activated(config, "viewer_deploy")
    assert not _is_activated(config, "viewer")
