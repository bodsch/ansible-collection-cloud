from __future__ import annotations, unicode_literals

import os

import testinfra.utils.ansible_runner
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="instance")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="collabora_office")


def test_directories(host, get_vars):

    dirs = [
        "/opt/cool",
        "/opt/cool/systemplate",
        "/opt/cool/child-roots",
        "/etc/coolwsd",
        "/usr/share/coolwsd",
        "/opt/collaboraoffice",
        "/opt/collaboraoffice/program",
        "/opt/collaboraoffice/presets",
        "/opt/collaboraoffice/share",
    ]

    for _dir in dirs:
        f = host.file(_dir)
        assert f.is_directory


def test_files(host, get_vars):

    files = [
        "/etc/default/coolwsd",
        "/etc/coolwsd/coolwsd.xml",
        "/lib/systemd/system/coolwsd.service",
        "/etc/systemd/system/multi-user.target.wants/coolwsd.service",
        "/opt/collaboraoffice/NOTICE",
        "/opt/collaboraoffice/program/oosplash",
        "/opt/collaboraoffice/presets/config/autotbl.fmt",
        "/opt/collaboraoffice/share/config/wizard/form/styles/water.css",
    ]

    for _file in files:
        f = host.file(_file)
        assert f.is_file


def test_user(host, get_vars):
    """ """
    user = "cool"
    group = "cool"

    assert host.group(group).exists
    assert host.user(user).exists
    assert group in host.user(user).groups


def test_service(host):
    service = host.service("coolwsd")
    assert service.is_enabled
    assert service.is_running


def test_open_port(host, get_vars):
    """ """
    for i in host.socket.get_listening_sockets():
        print(i)

    print(get_vars)

    service = host.socket("tcp://127.0.0.1:9980")
    assert service.is_listening
