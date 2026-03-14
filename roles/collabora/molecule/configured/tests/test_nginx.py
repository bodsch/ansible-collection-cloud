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
    service = host.service("nginx")

    assert service.is_enabled
    assert service.is_running


def test_fpm_pools(host, get_vars):
    """
    test sockets
    """
    for i in host.socket.get_listening_sockets():
        print(i)

    assert host.socket("tcp://0.0.0.0:80").is_listening
