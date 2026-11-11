"""Test the AON app's startup and per-request schema version selection."""

import asyncio
from types import SimpleNamespace
from typing import Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest
from geneweaver.aon import dependencies as deps


def _start(
    versions: list,
    latest: Optional[SimpleNamespace],
    default_schema: Optional[str] = None,
) -> Tuple[SimpleNamespace, dict]:
    """Run the app's lifespan startup against mocked schema versions; return the app."""
    managers = {None if v is None else v.id: MagicMock(name=f"sm{v}") for v in versions}
    if not managers:
        managers = {None: MagicMock(name="sm-none")}
    app = SimpleNamespace()

    async def enter() -> None:
        async with deps.lifespan(app):
            pass

    with (
        patch.object(deps, "get_schema_versions", return_value=list(versions)),
        patch.object(deps, "get_latest_schema_version", return_value=latest),
        patch.object(
            deps, "set_up_sessionmanager_by_schema", return_value=(managers, {})
        ),
        patch.object(deps.config, "DEFAULT_SCHEMA", default_schema),
    ):
        asyncio.run(enter())
    return app, managers


def _version(id_: int, name: str = "v", complete: bool = True) -> SimpleNamespace:
    return SimpleNamespace(id=id_, schema_name=name, load_complete=complete)


def test_startup_with_no_completed_load_does_not_crash(caplog) -> None:
    """A new database: the version table exists but nothing has loaded yet.

    The log line read ``.id`` off the missing version and aborted startup.
    """
    app, managers = _start(versions=[], latest=None)
    assert app.default_schema_version_id is None
    assert app.session is managers[None]
    assert "No completed AON data load" in caplog.text


def test_startup_uses_the_latest_completed_load() -> None:
    """With loads present, the latest completed one is the default."""
    v1, v8 = _version(1), _version(8)
    app, managers = _start(versions=[v8, v1], latest=v8)
    assert app.default_schema_version_id == 8
    assert app.session is managers[8]


def test_startup_with_an_unknown_default_schema_fails_clearly() -> None:
    """DEFAULT_SCHEMA naming no completed load is a configuration error, said so."""
    with pytest.raises(RuntimeError, match="not a completed AON data load"):
        _start(versions=[_version(8, "v8")], latest=None, default_schema="nope")
