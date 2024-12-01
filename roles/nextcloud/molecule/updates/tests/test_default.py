# coding: utf-8
from __future__ import unicode_literals

from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar

import json
import pytest
import os

import testinfra.utils.ansible_runner

HOST = 'instance'

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']).get_hosts(HOST)


def pp_json(json_thing, sort=True, indents=2):
    if type(json_thing) is str:
        print(json.dumps(json.loads(json_thing), sort_keys=sort, indent=indents))
    else:
        print(json.dumps(json_thing, sort_keys=sort, indent=indents))
    return None


def base_directory():
    """
    """
    cwd = os.getcwd()

    if 'group_vars' in os.listdir(cwd):
        directory = "../.."
        molecule_directory = "."
    else:
        directory = "."
        molecule_directory = f"molecule/{os.environ.get('MOLECULE_SCENARIO_NAME')}"

    return directory, molecule_directory


def read_ansible_yaml(file_name, role_name):
    """
    """
    read_file = None

    for e in ["yml", "yaml"]:
        test_file = f"{file_name}.{e}"
        if os.path.isfile(test_file):
            read_file = test_file
            break

    return f"file={read_file} name={role_name}"


@pytest.fixture()
def get_vars(host):
    """
        parse ansible variables
        - defaults/main.yml
        - vars/main.yml
        - vars/${DISTRIBUTION}.yaml
        - molecule/${MOLECULE_SCENARIO_NAME}/group_vars/all/vars.yml
    """
    base_dir, molecule_dir = base_directory()
    distribution = host.system_info.distribution
    operation_system = None

    if distribution in ['debian', 'ubuntu']:
        operation_system = "debian"
    elif distribution in ['redhat', 'ol', 'centos', 'rocky', 'almalinux']:
        operation_system = "redhat"
    elif distribution in ['arch', 'artix']:
        operation_system = f"{distribution}linux"

    # print(" -> {} / {}".format(distribution, os))
    # print(" -> {}".format(base_dir))

    file_defaults = read_ansible_yaml(f"{base_dir}/defaults/main", "role_defaults")
    file_vars = read_ansible_yaml(f"{base_dir}/vars/main", "role_vars")
    file_distibution = read_ansible_yaml(f"{base_dir}/vars/{operation_system}", "role_distibution")
    file_molecule = read_ansible_yaml(f"{molecule_dir}/group_vars/all/vars", "test_vars")
    # file_host_molecule = read_ansible_yaml("{}/host_vars/{}/vars".format(base_dir, HOST), "host_vars")

    defaults_vars = host.ansible("include_vars", file_defaults).get("ansible_facts").get("role_defaults")
    vars_vars = host.ansible("include_vars", file_vars).get("ansible_facts").get("role_vars")
    distibution_vars = host.ansible("include_vars", file_distibution).get("ansible_facts").get("role_distibution")
    molecule_vars = host.ansible("include_vars", file_molecule).get("ansible_facts").get("test_vars")
    # host_vars          = host.ansible("include_vars", file_host_molecule).get("ansible_facts").get("host_vars")

    ansible_vars = defaults_vars
    ansible_vars.update(vars_vars)
    ansible_vars.update(distibution_vars)
    ansible_vars.update(molecule_vars)
    # ansible_vars.update(host_vars)

    templar = Templar(loader=DataLoader(), variables=ansible_vars)
    result = templar.template(ansible_vars, fail_on_undefined=False)

    return result


def local_facts(host):
    """
      return local facts
    """
    return host.ansible("setup").get("ansible_facts").get("ansible_local").get("nextcloud")


def test_directories(host, get_vars):

    base_dir = get_vars.get("nextcloud_install_base_directory")
    version = local_facts(host).get("version")

    dirs = [
        base_dir,
        f"{base_dir}/nextcloud-{version}",
        f"{base_dir}/server/apps",
        f"{base_dir}/server/core",
        f"{base_dir}/server/config",
        f"{base_dir}/server/lib",
        f"{base_dir}/server/themes",
        f"{base_dir}/server/updater",
    ]

    # if 'latest' in install_dir:
    #     install_dir = install_dir.replace('latest', version)

    for _dir in dirs:
        f = host.file(_dir)
        assert f.is_directory


def test_files(host, get_vars):

    base_dir = get_vars.get("nextcloud_install_base_directory")

    files = [
        f"{base_dir}/server/occ",
        f"{base_dir}/server/config/config.php",
        f"{base_dir}/server/config/ansible.json",
        f"{base_dir}/server/config/config.json",
        f"{base_dir}/server/core/register_command.php",
        f"{base_dir}/server/core/signature.json",
    ]

    for _file in files:
        f = host.file(_file)
        assert f.is_file


def test_links(host, get_vars):

    base_dir = get_vars.get("nextcloud_install_base_directory")

    install_dir = f"{base_dir}/server"

    f = host.file(install_dir)
    assert f.is_symlink
