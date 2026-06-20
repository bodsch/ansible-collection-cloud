# coding: utf-8
"""
Validate the rendered /etc/nextcloud-ical-backup/config.toml on the instance.

The config is parsed once per test session (cached fixture) and then checked
structurally and semantically. Structural checks ensure required sections and
keys exist with correct types; semantic checks compare values against the
Ansible variables exposed via the `get_vars` fixture, so the test follows
your defaults rather than hard-coded duplicates.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
import yaml

from helper.molecule import get_vars, infra_hosts

testinfra_hosts = infra_hosts(host_name="instance")

CONFIG_PATH = "/etc/nextcloud-ical-backup/config.toml"


# --- fixtures --------------------------------------------------------------


@pytest.fixture(scope="module")
def config(host) -> dict[str, Any]:
    """
    Read and parse the runner configuration file once per module.

    :param host: testinfra host fixture
    :returns: parsed YAML document as a dict
    :raises AssertionError: if the file is missing or unparsable
    """
    f = host.file(CONFIG_PATH)
    assert f.exists, f"{CONFIG_PATH} does not exist"
    assert f.is_file, f"{CONFIG_PATH} is not a regular file"

    content = f.content_string
    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        pytest.fail(f"{CONFIG_PATH} is not valid YAML: {exc}")

    assert isinstance(parsed, dict), (
        f"{CONFIG_PATH} top-level must be a mapping, got {type(parsed).__name__}"
    )
    return parsed

# --- structural checks -----------------------------------------------------


def test_optional_nextcloud_path(config):
    """The `host` section is allowed to be empty/null but must be declared."""
    assert "nextcloud_path" in config
    assert config["nextcloud_path"] is None or isinstance(config["nextcloud_path"], str)
