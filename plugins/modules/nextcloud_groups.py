#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function
import os
import re
import json
import pwd
import grp

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.core.plugins.module_utils.module_results import results

__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'community'
}


class NextcloudGroups(object):
    """
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        self.groups = module.params.get("groups")
        self.working_dir = module.params.get("working_dir")
        self.owner = module.params.get("owner")

        self.occ_base_args = [
            "sudo",
            "--user",
            self.owner,
            "php",
            "occ"
        ]

    def run(self):
        """
        """
        self._occ = os.path.join(self.working_dir, 'occ')

        if not os.path.exists(self._occ):
            return dict(
                failed=True,
                changed=False,
                msg="missing occ"
            )

        os.chdir(self.working_dir)

        rc, installed, out, err = self.occ_check(check_installed=True)

        if not installed and rc == 1:
            return dict(
                failed=False,
                changed=False,
                msg=out
            )

        self.existing_groups = self.occ_list_groups()

        result_state = []

        if self.groups:
            for group in self.groups:
                group_state = group.get("state", "present")
                group_name = group.get("name", None)
                group_display_name = group.get("display_name", None)

                if group_name:
                    res = {}
                    if group_state == "present":
                        if group_name in self.existing_groups:
                            res[group_name] = dict(
                                changed=False,
                                msg="The group has already been created."
                            )
                        else:
                            res[group_name] = self.occ_create_group(name=group_name, display_name=group_display_name)
                    else:
                        if group_name in self.existing_groups:
                            res[group_name] = self.occ_remove_group(name=group_name)
                        else:
                            res[group_name] = dict(
                                changed=False,
                                msg="The group does not exist (anymore)."
                            )

                    result_state.append(res)

                else:
                    pass

        _state, _changed, _failed, state, changed, failed = results(self.module, result_state)

        result = dict(
            changed=_changed,
            failed=False,
            state=result_state
        )

        return result

    def occ_check(self, check_installed=False):
        """
            sudo -u www-data php occ check
        """
        # self.module.log(msg=f"occ_check({check_installed})")

        args = []
        args += self.occ_base_args

        args.append("check")
        args.append("--no-ansi")
        args.append("--output")
        args.append("json")

        # self.module.log(msg=f" args: '{args}'")

        rc, out, err = self.__exec(args, check_rc=False)

        """
            not installed: "Nextcloud is not installed - only a limited number of commands are available"
            installed: ''
        """
        # self.module.log(msg=f" rc : '{rc}'")
        # self.module.log(msg=f" out: '{out.strip()}'")
        # self.module.log(msg=f" err: '{err.strip()}'")

        if not check_installed:
            return rc, out, err

        installed = False

        if rc == 0:
            pattern = re.compile(r"Nextcloud is not installed.*", re.MULTILINE)
            # installed_out = re.search(pattern_1, out)
            is_installed = re.search(pattern, err)

            # self.module.log(msg=f" out: '{installed_out}'")
            # self.module.log(msg=f" err: '{is_installed}' {type(is_installed)}")

            if is_installed:
                installed = False
            else:
                installed = True

        else:
            err = out.strip()

            pattern = re.compile(r"An unhandled exception has been thrown:\n(?P<exception>.*)\n.*", re.MULTILINE)
            exception = re.search(pattern, err)

            if exception:
                err = exception.group("exception")

        # self.module.log(msg=f"{rc} '{installed}' '{out}' '{err}'")

        return (rc, installed, out, err)

    def occ_create_group(self, name, display_name=None):
        """
            sudo -u www-data php occ
                group:add
                --no-ansi
                --display-name="foo"
                "foo"
        """
        self.module.log(msg=f"occ_create_group({name}, {display_name})")
        _failed = True
        _changed = False

        args = []
        args += self.occ_base_args

        args.append("group:add")
        args.append("--no-ansi")
        # args.append("--output")
        # args.append("json")

        if display_name:
            args.append("--display-name")
            args.append(display_name)

        args.append(name)

        self.module.log(msg=f" args: '{args}'")

        rc, out, err = self.__exec(args, check_rc=False)

        # self.module.log(msg=f" rc : '{rc}'")
        # self.module.log(msg=f" out: {type(out)} - '{out.strip()}'")
        # self.module.log(msg=f" err: {type(err.strip())} - '{err.strip()}'")

        if rc == 0:
            _msg = "Group was successfully created."
            _failed = False
            _changed = True
        else:
            patterns = [
                'Group ".*" already exists.',
            ]
            error = None

            # out = json.loads(out)

            for pattern in patterns:
                filter_list = list(filter(lambda x: re.search(pattern, x), out.splitlines()))
                if len(filter_list) > 0 and isinstance(filter_list, list):
                    error = (filter_list[0]).strip()
                    self.module.log(msg=f"  - {error}")
                    break
            # self.module.log("--------------------")

            if rc == 0 and not error:
                _failed = False
                _changed = False
                _msg = f"Group {name} already created."
            else:
                _failed = False
                _changed = False
                _msg = error

        return dict(
            failed=_failed,
            changed=_changed,
            msg=_msg
        )

    def occ_remove_group(self, name):
        """
            sudo -u www-data php occ
                group:delete
                --no-ansi
                "foo"
        """
        self.module.log(msg=f"occ_remove_group({name})")
        _failed = True
        _changed = False

        args = []
        args += self.occ_base_args

        args.append("group:delete")
        args.append("--no-ansi")
        args.append(name)

        self.module.log(msg=f" args: '{args}'")

        rc, out, err = self.__exec(args, check_rc=False)

        # self.module.log(msg=f" rc : '{rc}'")
        # self.module.log(msg=f" out: {type(out)} - '{out.strip()}'")
        # self.module.log(msg=f" err: {type(err.strip())} - '{err.strip()}'")

        if rc == 0:
            _msg = "Group was successfully removed."
            _failed = False
            _changed = True
        else:
            patterns = [
                'Group ".*" already exists.',
            ]
            error = None

            # out = json.loads(out)

            for pattern in patterns:
                filter_list = list(filter(lambda x: re.search(pattern, x), out.splitlines()))
                if len(filter_list) > 0 and isinstance(filter_list, list):
                    error = (filter_list[0]).strip()
                    self.module.log(msg=f"  - {error}")
                    break
            # self.module.log("--------------------")

            if rc == 0 and not error:
                _failed = False
                _changed = False
                _msg = f"Group {name} already created."
            else:
                _failed = False
                _changed = False
                _msg = error

        return dict(
            failed=_failed,
            changed=_changed,
            msg=_msg
        )

    def occ_list_groups(self):
        """
        """
        args = []
        args += self.occ_base_args

        args.append("group:list")
        args.append("--no-ansi")
        args.append("--output")
        args.append("json")

        self.module.log(msg=f" args: '{args}'")

        rc, out, err = self.__exec(args, check_rc=False)

        out = json.loads(out)

        group_names = [x for x, _ in out.items()]
        return group_names

    def __file_state(self, file_name):
        """
        """
        current_owner = None
        current_group = None
        current_mode = None

        if os.path.exists(file_name):
            _state = os.stat(file_name)
            try:
                current_owner = pwd.getpwuid(_state.st_uid).pw_uid
            except KeyError:
                pass

            try:
                current_group = grp.getgrgid(_state.st_gid).gr_gid
            except KeyError:
                pass

            try:
                current_mode = oct(_state.st_mode)[-4:]
            except KeyError:
                pass

        return current_owner, current_group, current_mode

    def __exec(self, commands, check_rc=True):
        """
        """
        rc, out, err = self.module.run_command(commands, cwd=self.working_dir, check_rc=check_rc)

        # self.module.log(msg=f"  rc : '{rc}'")
        if rc != 0:
            self.module.log(msg=f"cmd: '{commands}'")
            self.module.log(msg=f"  rc : '{rc}'")
            self.module.log(msg=f"  out: '{out}'")
            self.module.log(msg=f"  err: '{err}'")
            for line in err.splitlines():
                self.module.log(msg=f"   {line}")

        return rc, out, err


def main():
    """
    """
    specs = dict(
        groups=dict(
            required=False,
            type=list,
            default=[]
        ),
        working_dir=dict(
            required=True,
            type=str
        ),
        owner=dict(
            required=False,
            type=str,
            default="www-data"
        ),
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=False,
    )

    kc = NextcloudGroups(module)
    result = kc.run()

    module.log(msg=f"= result : '{result}'")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()


"""
sudo --user www-data php occ group

Did you mean one of these?
    group:add
    group:adduser
    group:delete
    group:info
    group:list
    group:removeuser

sudo --user www-data php occ group:list --output=json
sudo --user www-data php occ group:add --no-ansi --help

Description:
  Add a group

Usage:
  group:add [options] [--] <groupid>

Arguments:
  groupid                          Group id

Options:
      --display-name=DISPLAY-NAME  Group name used in the web UI (can contain any characters)
  -h, --help                       Display help for the given command. When no command is given display help for the list command
  -q, --quiet                      Do not output any message
  -V, --version                    Display this application version
      --ansi|--no-ansi             Force (or disable --no-ansi) ANSI output
  -n, --no-interaction             Do not ask any interactive question
      --no-warnings                Skip global warnings, show command output only
  -v|vv|vvv, --verbose             Increase the verbosity of messages: 1 for normal output, 2 for more verbose output and 3 for debug
"""
