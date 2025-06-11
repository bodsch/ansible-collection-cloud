#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2021-2025, Bodo Schulz <bodo@boone-schulz.de>
# BSD 2-clause (see LICENSE or https://opensource.org/licenses/BSD-2-Clause)

from __future__ import absolute_import, print_function
# import os
import re
# import shutil
# import pwd
# import grp
import json

# from ansible_collections.bodsch.core.plugins.module_utils.checksum import Checksum
from ansible_collections.bodsch.cloud.plugins.module_utils.nextcloud.occ import Occ


class NextcloudIdentity(Occ):
    """
    """
    module = None

    def __init__(self, module, owner, working_dir):
        """
        """
        super().__init__(module, owner, working_dir)  # Ruft den Konstruktor der Basisklasse Occ auf

        self.module = module

        self.module.log(f"NextcloudIdentity::__init__({owner}, {working_dir})")

        self.owner = owner
        self.working_dir = working_dir

    def identities(self):
        """
        """
        self.module.log("NextcloudIdentity::identities()")

        self.existing_users = self.list_users()
        self.existing_groups = self.list_groups()

        return (self.existing_users, self.existing_groups)

    def create_user(self, user_data: dict = {}) -> dict:
        """
            sudo -u www-data php occ
                user:add
                --no-ansi
                --display-name="foo"
                "foo"
        """
        self.module.log(f"NextcloudIdentity::create_user({user_data})")

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

        rc, out, err = self._exec(args, check_rc=False)

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

    def reset_password(self, user_data={}):
        """
            sudo -u www-data php occ
                user:resetpassword
                --no-ansi
                --password-from-env
                "foo"
        """
        self.module.log(f"NextcloudIdentity::reset_password({user_data})")

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

        rc, out, err = self._exec(args, check_rc=False)

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

    def remove_user(self, name):
        """
            sudo -u www-data php occ
                user:delete
                --no-ansi
                "foo"
        """
        self.module.log(f"NextcloudIdentity::remove_user({name})")

        _failed = True
        _changed = False
        _msg = ""

        args = []
        args += self.occ_base_args

        args.append("user:delete")
        args.append("--no-ansi")
        args.append(name)

        self.module.log(msg=f" args: '{args}'")

        rc, out, err = self._exec(args, check_rc=False)

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

    def list_users(self) -> list:
        """
        """
        self.module.log("NextcloudIdentity::list_users()")

        args = []
        args += self.occ_base_args

        args.append("user:list")
        args.append("--no-ansi")
        args.append("--output")
        args.append("json")

        rc, out, err = self._exec(args, check_rc=False)
        out = json.loads(out)

        user_names = [x for x, _ in out.items()]
        return user_names

    def user_settings(self, username, user_settings):
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
                  --default-value=DEFAULT-VALUE  (Only applicable on get) If no default value is set and the
                                                 config does not exist, the command will exit with 1
                  --update-only                  Only updates the value, if it is not set before, it is not being added
                  --delete                       Specify this option to delete the config
                  --error-if-not-exists          Checks whether the setting exists before deleting it
        """
        self.module.log(msg=f"NextcloudIdentity::user_settings({username}, {user_settings})")

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
                        result[app][key] = self.add_user_settings(username=username, app=app, key=key, value=value)
                        result_arr.append(result)
        # self.module.log(msg=f"    - {result_arr}")
        return (_failed, _changed, _msg)

    def user_info(self, username):
        """
            sudo -u www-data php occ
                user:info
                --no-ansi
                --output json
                bob
        """
        self.module.log(msg=f"NextcloudIdentity::user_info({username})")

        args = []
        args += self.occ_base_args

        args.append("user:info")
        args.append("--no-ansi")
        args.append("--output")
        args.append("json")
        args.append(username)

        rc, out, err = self._exec(args, check_rc=False)

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

    def add_user_to_group(self, username, groups):
        """
        """
        self.module.log(msg=f"NextcloudIdentity::user_to_group({username}, {groups})")

        _group_added = []
        for group in groups:
            args = []
            args += self.occ_base_args

            args.append("group:adduser")
            args.append("--no-ansi")
            args.append(group)
            args.append(username)

            rc, out, err = self._exec(args, check_rc=False)

            if rc == 0:
                _group_added.append(group)
            else:
                pass

        # self.module.log(msg=f"= {_group_added}")
        return _group_added

    def delete_user_from_group(self, username, groups):
        """
        """
        self.module.log(msg=f"NextcloudIdentity::delete_user_from_group({username}, {groups})")
        _group_removed = []

        for group in groups:
            args = []
            args += self.occ_base_args

            args.append("group:removeuser")
            args.append("--no-ansi")
            args.append(group)
            args.append(username)

            rc, out, err = self._exec(args, check_rc=False)

            if rc == 0:
                _group_removed.append(group)
            else:
                pass

        # self.module.log(msg=f"= {_group_removed}")
        return _group_removed

    def add_user_settings(self, username, app, key, value):
        """
        """
        self.module.log(msg=f"NextcloudIdentity::add_user_settings({username}, {app}, {key}, {value})")

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

        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            return True
        else:
            self.module.log(msg=f"__add_user_settings({username}, {app}, {key}, {value})")
            self.module.log(msg=f"WARNING: {out}")
            return False

        # self.module.log(msg=f"= {_group_added}")
        return None

    def list_groups(self) -> list:
        """
        """
        self.module.log("NextcloudIdentity::list_groups()")

        args = []
        args += self.occ_base_args

        args.append("group:list")
        args.append("--no-ansi")
        args.append("--output")
        args.append("json")

        rc, out, err = self._exec(args, check_rc=False)
        out = json.loads(out)

        group_names = [x for x, _ in out.items()]

        return group_names

    def user_groups(self, username, groups):
        """
            add user to group(s)
            remove user from group(s)

            sudo -u www-data php occ
                user:delete
                --no-ansi
                "foo"
        """
        self.module.log(msg=f"NextcloudIdentity::user_groups({username}, {groups})")
        _failed = True
        _changed = False
        _msg = ""

        _state = self.user_info(username)
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
            _group_added = self.add_user_to_group(username=username, groups=groups_missing)

        if len(groups_removing) > 0:
            _group_removed = self.delete_user_from_group(username=username, groups=groups_removing)

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

    def create_group(self, name, display_name=None):
        """
            sudo -u www-data php occ
                group:add
                --no-ansi
                --display-name="foo"
                "foo"
        """
        self.module.log(msg=f"NextcloudIdentity::create_group({name}, {display_name})")
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

        rc, out, err = self._exec(args, check_rc=False)

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

    def remove_group(self, name):
        """
            sudo -u www-data php occ
                group:delete
                --no-ansi
                "foo"
        """
        self.module.log(msg=f"NextcloudIdentity::remove_group({name})")
        _failed = True
        _changed = False

        args = []
        args += self.occ_base_args

        args.append("group:delete")
        args.append("--no-ansi")
        args.append(name)

        self.module.log(msg=f" args: '{args}'")

        rc, out, err = self._exec(args, check_rc=False)

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
