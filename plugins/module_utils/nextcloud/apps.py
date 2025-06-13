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
from ansible_collections.bodsch.core.plugins.module_utils.module_results import results


class NextcloudApps(Occ):
    """
    """
    module = None

    def __init__(self, module, owner, working_dir):
        """
        """
        super().__init__(module, owner, working_dir)

        self.module = module

        # self.module.log(f"NextcloudApps::__init__({owner}, {working_dir})")

        self.owner = owner
        self.working_dir = working_dir

    def install_app(self, app_name):
        """
        """
        # self.module.log(f"NextcloudApps::install_app({app_name})")

        _failed = True
        _changed = False
        _msg = ""

        args = []
        args += self.occ_base_args

        args.append("app:install")
        args.append("--no-ansi")
        args.append("--keep-disabled")
        args.append(app_name)

        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            _msg = "App was successfully installed."
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

    def remove_app(self, app_name):
        """
        """
        # # self.module.log(f"NextcloudApps::remove_app({app_name})")
        _failed = True
        _changed = False
        _msg = ""

        args = []
        args += self.occ_base_args

        args.append("app:remove")
        args.append("--no-ansi")
        args.append(app_name)

        # self.module.log(msg=f" args: '{args}'")

        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            _msg = "App was successfully removed."
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

    def path_app(self, app_name):
        """
        """
        # self.module.log(f"NextcloudApps::path_app({app_name})")
        _failed = True
        _changed = False

        args = []
        args += self.occ_base_args

        args.append("app:getpath")
        args.append("--no-ansi")
        args.append(app_name)

        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            _installed = True
            _failed = False
            _changed = True
        else:
            _installed = False
            _failed = True
            _changed = False

        return (_failed, _changed, _installed)

    def enable_app(self, app_name, groups=[]):
        """
        """
        # self.module.log(f"NextcloudApps::enable_app({app_name}, {groups})")
        _failed = True
        _changed = False
        _msg = ""

        args = []
        args += self.occ_base_args

        args.append("app:enable")
        args.append("--no-ansi")
        args.append(app_name)

        if len(groups):
            for g in groups:
                args.append("--groups")
                args.append(g)

        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            _msg = "App was successfully enabled."
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

    def disable_app(self, app_name):
        """
        """
        # self.module.log(f"NextcloudApps::disable_app({app_name})")
        _failed = True
        _changed = False
        _msg = ""

        args = []
        args += self.occ_base_args

        args.append("app:disable")
        args.append("--no-ansi")
        args.append(app_name)

        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            _msg = "App was successfully disabled."
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

    def app_settings(self, app_name, app_settings):
        """
            sudo --preserve-env --user www-data
                php occ config:app:get
                    richdocuments disable_certificate_verification
            sudo --preserve-env --user www-data
                php occ config:app:set
                    --output json --value yes --update-only richdocuments disable_certificate_verification
        """
        # # self.module.log(f"NextcloudApps::app_settings({app_name}, {app_settings})")

        failed = False
        changed = False
        # msg = "not to do."
        result_state = []

        for config_key, config_value in app_settings.items():
            res = {}
            # self.module.log(msg=f"  - {config_key}  -> {config_value})")

            if isinstance(config_value, bool):
                config_value = 'yes' if config_value else 'no'

            if not isinstance(config_value, str):
                self.module.log(msg=f"ignore value {config_value} for key {config_key}")
                continue

            args = []
            args += self.occ_base_args

            args.append("config:app:set")
            args.append("--no-ansi")
            args.append("--output")
            args.append("json")
            args.append("--value")
            args.append(config_value)
            args.append(app_name)
            args.append(config_key)

            # self.module.log(msg=f" args: '{args}'")

            rc, out, err = self._exec(args, check_rc=False)

            if rc == 0:
                _msg = f"config value for {config_key} was successfully set to {config_value}."
                _failed = False
                _changed = True
            else:
                _failed = True
                _changed = False
                _msg = out.strip()

            res[app_name] = dict(
                changed=_changed,
                msg=_msg
            )

        _state, _changed, _failed, state, changed, failed = results(self.module, result_state)

        result = dict(
            changed=_changed,
            failed=failed,
            msg=result_state
        )

        return result

        # return (_failed, _changed, result_state)

    def list_apps(self):
        """
        """
        # self.module.log(f"NextcloudApps::list_apps()")

        app_names = []
        args = []
        args += self.occ_base_args

        args.append("app:list")
        args.append("--no-ansi")
        args.append("--output")
        args.append("json")

        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            out = json.loads(out)

            app_names = out

        enabled_apps = [x for x, _ in app_names.get("enabled", {}).items()]
        disabled_apps = [x for x, _ in app_names.get("disabled", {}).items()]

        # self.module.log(f"existing_apps : {app_names}")
        # self.module.log(f"enabled apps  : {enabled_apps}")
        # self.module.log(f"disabled apps : {disabled_apps}")

        return (app_names, enabled_apps, disabled_apps)

    def check_for_updates(self, check_installed=False):
        """
        """
        # self.module.log(f"NextcloudApps::check_for_updates({check_installed})")

        # app_names = []
        res = dict()
        update = False
        args = []
        args += self.occ_base_args

        args.append("update:check")
        args.append("--no-ansi")

        rc, out, err = self._exec(args, check_rc=False)

        # self.module.log(msg=f"rc: {rc}, out: {out.strip()}, err: {err.strip()}")
        # self.module.log(msg=f"  {len(out)}")
        # self.module.log(msg=f"  {len(err)}")

        if rc == 0:
            pattern = re.compile(r"Update for (?P<app>.*) to version (?P<version>.*) is available.*", flags=re.MULTILINE)  # | re.DOTALL)

            for match in pattern.finditer(out):
                # self.module.log(f"match : {match}")
                app, version = match.groups()
                # self.module.log(f"  - {app} : {version}")
                res.update({app: version})

        update = len(res) >= 1

        # self.module.log(msg=f"= (rc: {rc}, update: {update}, out: {res}, err: {err})")

        return (rc, update, res, err)

    def update_app(self, app_name):
        """
        """
        # self.module.log(f"NextcloudApps::update_app({app_name})")

        # _failed = True
        # _changed = False
        # _msg = ""

        args = []
        args += self.occ_base_args

        args.append("app:update")
        args.append("--no-ansi")
        args.append(app_name)

        # self.module.log(msg=f"args: {args}")

        rc, out, err = self._exec(args, check_rc=False)

        return (rc, out, err)
