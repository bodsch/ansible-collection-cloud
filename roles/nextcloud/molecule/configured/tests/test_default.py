from __future__ import annotations, unicode_literals

import os

import testinfra.utils.ansible_runner
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="instance")

# --- tests -----------------------------------------------------------------


def test_directories(host, get_vars):
    """ """
    _facts = local_facts(host=host, fact="nextcloud")

    base_dir = get_vars.get("nextcloud_install_base_directory")
    version = _facts.get("version")

    dirs = [
        base_dir,
        f"{base_dir}/nextcloud/{version}",
        f"{base_dir}/nextcloud/config",
        f"{base_dir}/nextcloud/server/apps",
        f"{base_dir}/nextcloud/server/core",
        f"{base_dir}/nextcloud/server/config",
        f"{base_dir}/nextcloud/server/lib",
        f"{base_dir}/nextcloud/server/themes",
        f"{base_dir}/nextcloud/server/updater",
    ]

    # if 'latest' in install_dir:
    #     install_dir = install_dir.replace('latest', version)

    for _dir in dirs:
        f = host.file(_dir)
        assert f.is_directory


def test_data_directory(host, get_vars):

    nc_defaults = get_vars.get("nextcloud_defaults", {})
    data_directory = nc_defaults.get("data_directory")

    f = host.file(data_directory)
    assert f.is_directory


def test_files(host, get_vars):

    base_dir = get_vars.get("nextcloud_install_base_directory")

    files = [
        f"{base_dir}/nextcloud/server/occ",
        f"{base_dir}/nextcloud/server/config/config.php",
        f"{base_dir}/nextcloud/server/config/ansible.json",
        f"{base_dir}/nextcloud/server/core/register_command.php",
        f"{base_dir}/nextcloud/server/core/signature.json",
        f"{base_dir}/nextcloud/config/config.php",
        f"{base_dir}/nextcloud/config/config.json",
        f"{base_dir}/nextcloud/config/ansible.json",
    ]

    for _file in files:
        f = host.file(_file)
        assert f.is_file


def test_links_to_server(host, get_vars):

    base_dir = get_vars.get("nextcloud_install_base_directory")

    install_dir = f"{base_dir}/nextcloud/server"

    f = host.file(install_dir)
    assert f.is_symlink


def test_links_to_config(host, get_vars):
    """ """
    _facts = local_facts(host=host, fact="nextcloud")
    base_dir = get_vars.get("nextcloud_install_base_directory")
    version = _facts.get("version")

    install_dir = f"{base_dir}/nextcloud/{version}/config"

    f = host.file(install_dir)
    assert f.is_symlink
