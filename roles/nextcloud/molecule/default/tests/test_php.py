from __future__ import annotations, unicode_literals

import os

import testinfra.utils.ansible_runner
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="instance")

# --- tests -----------------------------------------------------------------


def test_service(host):
    """
    is service running and enabled
    """
    service = host.service(local_facts(host).get("daemon"))

    assert service.is_enabled
    assert service.is_running


def test_fpm_pools(host, get_vars):
    """
    test sockets
    """
    for i in host.socket.get_listening_sockets():
        print(i)

    distribution = host.system_info.distribution
    release = host.system_info.release

    socket_name = "/run/php/worker-01.sock"

    f = host.file(socket_name)
    assert f.exists

    if not (distribution == "ubuntu" and release == "18.04"):
        assert host.socket(f"unix://{socket_name}").is_listening
