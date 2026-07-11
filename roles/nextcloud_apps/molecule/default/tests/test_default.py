from __future__ import annotations, unicode_literals

import testinfra.utils.ansible_runner
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="instance")

# --- tests -----------------------------------------------------------------


def test_data_directory(host, get_vars):

    nc_defaults = get_vars.get("nextcloud_defaults", {})
    data_directory = nc_defaults.get("data_directory", None)

    if data_directory:
        f = host.file(data_directory)
        assert f.is_directory
