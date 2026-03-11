
from __future__ import annotations, unicode_literals

import os

import testinfra.utils.ansible_runner
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="instance")

# --- tests -----------------------------------------------------------------


def test_directories(host, get_vars):

    dirs = ["/usr/local/opt/calcardbackup", "/etc/calcardbackup"]

    for _dir in dirs:
        f = host.file(_dir)
        assert f.is_directory


def test_files(host, get_vars):

    files = [
        "/etc/calcardbackup/calcardbackup.conf",
        "/usr/bin/calcardbackup",
        "/usr/lib/systemd/system/calcardbackup.timer",
        "/usr/lib/systemd/system/calcardbackup.service",
    ]

    for _file in files:
        f = host.file(_file)
        assert f.is_file
