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


class NextcloudUsers(object):
    """
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        self.users = module.params.get("users")
        self.working_dir = module.params.get("working_dir")
        self.owner = module.params.get("owner")

        self.occ_base_args = [
            "sudo",
            "--preserve-env",
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

        # self.module.log(msg=f" rc : '{rc}'")
        # self.module.log(msg=f" out: '{out.strip()}'")
        # self.module.log(msg=f" err: '{err.strip()}'")

        if not installed and rc == 1:
            return dict(
                failed=False,
                changed=False,
                msg=out
            )

        self.existing_groups = self.occ_list_groups()
        self.existing_users = self.occ_list_users()

        # self.module.log(f"existing_groups: {self.existing_groups}")
        # self.module.log(f"existing_users : {self.existing_users}")

        result_state = []

        if self.users:
            for user in self.users:
                """
                """
                # self.module.log(f" - {user}")

                user_state = user.get("state", "present")
                user_name = user.get("name", None)
                # user_password = user.get("password", None)
                resetpassword = user.get("resetpassword", None)
                # user_display_name = user.get("display_name", None)
                user_groups = user.get("groups", [])
                user_settings = user.get("settings", [])

                if user_name:
                    res = {}
                    if user_state == "present":

                        if user_name in self.existing_users:
                            if resetpassword:
                                res[user_name] = self.occ_reset_password(user_data=user)
                            else:
                                res[user_name] = dict(
                                    changed=False,
                                    msg="The user has already been created."
                                )
                        else:
                            res[user_name] = self.occ_create_user(user_data=user)

                        _group_failed, _group_changed, _group_msg = self.occ_user_groups(username=user_name, groups=user_groups)

                        if not _group_failed and _group_changed:
                            res[user_name]["msg"] += _group_msg

                        _settings_failed, _settings_changed, _settings_msg = self.occ_user_settings(username=user_name, user_settings=user_settings)

                    else:
                        if user_name in self.existing_users:
                            res[user_name] = self.occ_remove_user(name=user_name)
                        else:
                            res[user_name] = dict(
                                changed=False,
                                msg="The user does not exist (anymore)."
                            )

                    result_state.append(res)

                else:
                    pass

        _state, _changed, _failed, state, changed, failed = results(self.module, result_state)

        # self.module.log(msg=f" - state   {_state} '{state}'")
        # self.module.log(msg=f" - changed {_changed} '{changed}'")
        # self.module.log(msg=f" - failed  {_failed} '{failed}'")

        result = dict(
            changed=_changed,
            failed=False,
            state=result_state
        )

        # self.module.log(msg=f" = {result}")

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
                err = exception.user("exception")

        # self.module.log(msg=f"{rc} '{installed}' '{out}' '{err}'")

        return (rc, installed, out, err)

    def occ_create_user(self, user_data={}):
        """
            sudo -u www-data php occ
                user:add
                --no-ansi            if len(groups) > 0:
                _groups = self.occ_add_user_to_groups(username=name, groups=groups)
                --display-name="foo"
                "foo"
        """
        # self.module.log(msg=f"occ_create_user({user_data})")
        _failed = True
        _changed = False
        _msg = ""

        name = user_data.get("name", None)
        display_name = user_data.get("display_name", None)
        password = user_data.get("password", None)

        args = []
        args += self.occ_base_args

        args.append("user:add")

        if password:
            self.module.run_command_environ_update = {"OC_PASS": password}
            args.append("--password-from-env")

        if display_name:
            args.append("--display-name")
            args.append(display_name)

        args.append("--no-ansi")
        args.append(name)

        rc, out, err = self.__exec(args, check_rc=False)

        if rc == 0:
            _msg = "User was successfully created."
            _failed = False
            _changed = True
        else:
            _failed = True
            _changed = False
            _msg = out.strip()

        return dict(
            failed=_failed,
            changed=_changed,
            msg=_msg
        )

    def occ_reset_password(self, user_data={}):
        """
            sudo -u www-data php occ
                user:resetpassword
        # self.module.log(msg=f" rc : '{rc}'")
        # self.module.log(msg=f" out: {type(out)} - '{out.strip()}'")
        # self.module.log(msg=f" err: {type(err.strip())} - '{err.strip()}'")

                --no-ansi
                --password-from-env
                "foo"
        """
        # self.module.log(msg=f"occ_reset_password({user_data})")
        _failed = True
        _changed = False
        _msg = ""

        name = user_data.get("name", None)
        password = user_data.get("password", None)

        args = []
        args += self.occ_base_args

        args.append("user:resetpassword")
        args.append("--no-ansi")

        if password:
            self.module.run_command_environ_update = {"OC_PASS": password}
            args.append("--password-from-env")

        args.append(name)

        rc, out, err = self.__exec(args, check_rc=False)

        if rc == 0:
            _msg = f"{out.strip()}."
            _failed = False
            _changed = True
        else:
            _failed = True
            _changed = False
            _msg = f"{err.strip()}."

        return dict(
            failed=_failed,
            changed=_changed,
            msg=_msg
        )

    def occ_remove_user(self, name):
        """
            sudo -u www-data php occ
                user:delete
                --no-ansi
                "foo"
        """
        # self.module.log(msg=f"occ_remove_user({name})")
        _failed = True
        _changed = False
        _msg = ""

        args = []
        args += self.occ_base_args

        args.append("user:delete")
        args.append("--no-ansi")
        args.append(name)

        self.module.log(msg=f" args: '{args}'")

        rc, out, err = self.__exec(args, check_rc=False)

        # self.module.log(msg=f" rc : '{rc}'")
        # self.module.log(msg=f" out: {type(out)} - '{out.strip()}'")
        # self.module.log(msg=f" err: {type(err.strip())} - '{err.strip()}'")

        if rc == 0:
            _msg = "User was successfully removed."
            _failed = False
            _changed = True
        else:
            _failed = True
            _changed = False
            _msg = out.strip()

        return dict(
            failed=_failed,
            changed=_changed,
            msg=_msg
        )

    def occ_list_users(self):
        """
        """
        args = []
        args += self.occ_base_args

        args.append("user:list")
        args.append("--no-ansi")
        args.append("--output")
        args.append("json")

        rc, out, err = self.__exec(args, check_rc=False)
        out = json.loads(out)

        user_names = [x for x, _ in out.items()]
        return user_names

    def occ_list_groups(self):
        """
        """
        args = []
        args += self.occ_base_args

        args.append("group:list")
        args.append("--no-ansi")
        args.append("--output")
        args.append("json")

        rc, out, err = self.__exec(args, check_rc=False)
        out = json.loads(out)

        group_names = [x for x, _ in out.items()]
        return group_names

    def occ_user_groups(self, username, groups):
        """
            add user to group(s)
            remove user from group(s)

            sudo -u www-data php occ
                user:delete
                --no-ansi
                "foo"
        """
        # self.module.log(msg=f"occ_user_groups({username}, {groups})")
        _failed = True
        _changed = False
        _msg = ""

        _state = self.occ_user_info(username)
        user_state = _state.get("state", "absent")

        if user_state == "absent":
            return (_failed, _changed, f"The User {username} has not yet been created.")

        # user is current in groups
        user_groups = _state.get("groups", [])

        # invalid groups
        groups_invalid = list(set(groups) - set(self.existing_groups))

        # valid groups for this user, remove not exists groups
        valid_user_groups = [x for x in self.existing_groups if x in groups]

        # user ist NOT in group
        groups_missing = [x for x in valid_user_groups if x not in user_groups]

        # user should removed from group
        groups_removing = [x for x in user_groups if x not in groups]

        # self.module.log(msg=f"{username} : {user_state}")
        # self.module.log(msg=f"  - groups exists: {self.existing_groups}")
        # self.module.log(msg=f"    - is in groups: {user_groups}")
        # self.module.log(msg=f"    - should in groups: {groups}")
        # self.module.log(msg=f"    - valid user groups: {valid_user_groups}")
        # self.module.log(msg=f"    - groups missing: {groups_missing}")
        # self.module.log(msg=f"    - remove from groups: {groups_removing}")
        # self.module.log(msg=f"    - groups invalid: {groups_invalid}")
        _group_added = []
        _group_removed = []
        _group_skipped = groups_invalid
        m = []

        if len(groups_missing) > 0:
            _group_added = self.__add_user_to_group(username=username, groups=groups_missing)

        if len(groups_removing) > 0:
            _group_removed = self.__delete_user_from_group(username=username, groups=groups_removing)

        if len(_group_removed) > 0 or len(_group_added) > 0:
            _failed = False
            _changed = True

            if len(_group_added) > 0:
                added = ", ".join(_group_added)
                m.append(f" Added to group(s): {added}.")

            if len(_group_removed) > 0:
                removed = ", ".join(_group_removed)
                m.append(f" Removed from group(s): {removed}.")

        if len(_group_skipped) > 0:
            skipped = ", ".join(_group_skipped)
            m.append(f"Group(s) {skipped} does not exist, was skipped.")

        _msg = " ".join(m)

        return (_failed, _changed, _msg)

    def occ_user_settings(self, username, user_settings):
        """
            add settings for user

            sudo -u www-data php occ
                user:setting
                --no-ansi
                ...

            Description:
              Read and modify user settings

            Usage:
              user:setting [options] [--] <uid> [<app> [<key> [<value>]]]

            Arguments:
              uid                                User ID used to login
              app                                Restrict the settings to a given app [default: ""]
              key                                Setting key to set, get or delete [default: ""]
              value                              The new value of the setting

            Options:
                  --output[=OUTPUT]              Output format (plain, json or json_pretty, default is plain) [default: "plain"]
                  --ignore-missing-user          Use this option to ignore errors when the user does not exist
                  --default-value=DEFAULT-VALUE  (Only applicable on get)
                                                 If no default value is set and the config does not exist, the command will exit with 1
                  --update-only                  Only updates the value, if it is not set before, it is not being added
                  --delete                       Specify this option to delete the config
                  --error-if-not-exists          Checks whether the setting exists before deleting it
        """
        # self.module.log(msg=f"occ_user_settings({username}, {user_settings})")
        _failed = True
        _changed = False
        _msg = ""

        result_arr = []

        for app_setting in user_settings:
            # self.module.log(msg=f"- {app_setting}")
            for app, settings in app_setting.items():
                result = dict()
                result[app] = dict()
                # self.module.log(msg=f"  {app}:  ({settings} - {type(settings)})")
                if isinstance(settings, dict):
                    for key, value in settings.items():
                        # self.module.log(msg=f"    - {key}: {value}")
                        result[app][key] = self.__add_user_settings(username=username, app=app, key=key, value=value)
                        result_arr.append(result)
        # self.module.log(msg=f"    - {result_arr}")
        return (_failed, _changed, _msg)

    def occ_user_info(self, username):
        """
            sudo -u www-data php occ
                user:info
                --no-ansi
                --output json
                bob
        """
        # self.module.log(msg=f"occ_user_info({username})")

        args = []
        args += self.occ_base_args

        args.append("user:info")
        args.append("--no-ansi")
        args.append("--output")
        args.append("json")
        args.append(username)

        rc, out, err = self.__exec(args, check_rc=False)

        if rc == 0:
            out = json.loads(out)
            out.update({"state": "present"})
        else:
            out = dict(
                user_id=username,
                state="absent",
                msg=out.strip()
            )

        return out

    def __add_user_to_group(self, username, groups):
        """
        """
        # self.module.log(msg=f"__add_user_to_group({username}, {groups})")
        _group_added = []
        for group in groups:
            args = []
            args += self.occ_base_args

            args.append("group:adduser")
            args.append("--no-ansi")
            args.append(group)
            args.append(username)

            rc, out, err = self.__exec(args, check_rc=False)

            if rc == 0:
                _group_added.append(group)
            else:
                pass

        # self.module.log(msg=f"= {_group_added}")
        return _group_added

    def __delete_user_from_group(self, username, groups):
        """
        """
        # self.module.log(msg=f"__delete_user_from_group({username}, {groups})")
        _group_removed = []

        for group in groups:
            args = []
            args += self.occ_base_args

            args.append("group:removeuser")
            args.append("--no-ansi")
            args.append(group)
            args.append(username)

            rc, out, err = self.__exec(args, check_rc=False)

            if rc == 0:
                _group_removed.append(group)
            else:
                pass

        # self.module.log(msg=f"= {_group_removed}")
        return _group_removed

    def __add_user_settings(self, username, app, key, value):
        """
        """
        # self.module.log(msg=f"__add_user_settings({username}, {app}, {key}, {value})")
        args = []
        args += self.occ_base_args

        args.append("user:setting")
        args.append("--no-ansi")
        args.append("--output")
        args.append("json")
        args.append(username)
        args.append(app)
        args.append(key)
        args.append(str(value))

        rc, out, err = self.__exec(args, check_rc=False)

        if rc == 0:
            return True
        else:
            self.module.log(msg=f"__add_user_settings({username}, {app}, {key}, {value})")
            self.module.log(msg=f"WARNING: {out}")
            return False

        # self.module.log(msg=f"= {_group_added}")
        return None

    def __file_state(self, file_name):
        """
        """
        current_owner = None
        current_user = None
        current_mode = None

        if os.path.exists(file_name):
            _state = os.stat(file_name)
            try:
                current_owner = pwd.getpwuid(_state.st_uid).pw_uid
            except KeyError:
                pass

            try:
                current_user = grp.getgrgid(_state.st_gid).gr_gid
            except KeyError:
                pass

            try:
                current_mode = oct(_state.st_mode)[-4:]
            except KeyError:
                pass

        return current_owner, current_user, current_mode

    def __exec(self, commands, check_rc=True):
        """
        """
        rc, out, err = self.module.run_command(
            commands,
            cwd=self.working_dir,
            check_rc=check_rc)

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
        users=dict(
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

    kc = NextcloudUsers(module)
    result = kc.run()

    module.log(msg=f"= result : '{result}'")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()


"""
sudo --user www-data php occ user

Did you mean one of these?
    group:adduser
    group:removeuser
    user:add
    user:add-app-password
    user:auth-tokens:add
    user:auth-tokens:delete
    user:auth-tokens:list
    user:delete
    user:disable
    user:enable
    user:info
    user:lastseen
    user:list
    user:report
    user:resetpassword
    user:setting
    user:sync-account-data

sudo --user www-data php occ user:list --output=json
sudo --user www-data php occ user:add --no-ansi --help
"""
