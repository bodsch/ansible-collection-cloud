#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2021-2025, Bodo Schulz <bodo@boone-schulz.de>
# BSD 2-clause (see LICENSE or https://opensource.org/licenses/BSD-2-Clause)

from __future__ import absolute_import, print_function
import os
import re
import json
import shutil


class Occ():
    """
    """
    module = None

    def __init__(self, module: any, owner: str, working_dir: str):
        """
        """
        self.module = module

        # self.module.log(f"Occ::__init__({owner}, {working_dir})")

        self.owner = owner
        self.working_dir = working_dir
        self._occ = os.path.join(self.working_dir, 'occ')

        self.occ_base_args = [
            "sudo",
            "--user",
            self.owner,
            "php",
            "occ"
        ]

    def self_check(self):
        """
        """
        self.module.log("Occ::self_check()")

        # self.module.log(msg=f" console   : '{self._occ}'")

        error = False
        msg = dict()

        if not os.path.exists(self._occ):
            error = True
            msg = dict(
                failed=True,
                changed=False,
                msg="missing occ"
            )

        if os.path.exists(self.working_dir):
            os.chdir(self.working_dir)
        else:
            error = True
            msg = dict(
                failed=True,
                changed=False,
                msg=f"missing working directory '{self.working_dir}'"
            )

        return error, msg

    def status(self) -> (int, bool, str, bool, str):
        """
            sudo -u www-data php occ status
        """
        self.module.log("Occ::status()")

        installed = False
        version_string = None

        args = []
        args += self.occ_base_args

        args.append("status")
        args.append("--no-ansi")
        args.append("--output")
        args.append("json")

        rc, out, err = self._exec(args, check_rc=False)

        # self.module.log(msg=f" rc : '{rc}'")
        # self.module.log(msg=f" out: '{out.strip()}'")
        # self.module.log(msg=f" err: '{err.strip()}'")

        if rc == 0:
            out = json.loads(out)
            installed = out.get("installed", False)
            # version_full = out.get("version", None)
            version_string = out.get("versionstring", None)
            db_upgrade = out.get("needsDbUpgrade", False)
        else:
            err = out.strip()

            pattern = re.compile(r"An unhandled exception has been thrown:\n(?P<exception>.*)\n.*", re.MULTILINE)
            exception = re.search(pattern, err)

            if exception:
                err = exception.group("exception")

        return (rc, installed, version_string, db_upgrade, err)

    def upgrade(self):
        """
        """
        # self.module.log("Occ::upgrade()")
        pass

    def check(self, check_installed: bool = False) -> (int, bool, str, str):
        """
            sudo -u www-data php occ check
        """
        # self.module.log(f"Occ::check({check_installed})")
        # self.module.log(msg="occ_check()")

        installed = False

        args = []
        args += self.occ_base_args

        args.append("check")
        args.append("--no-ansi")
        args.append("--output")
        args.append("json")

        rc, out, err = self._exec(args, check_rc=False)

        """
            not installed: "Nextcloud is not installed - only a limited number of commands are available"
            Nextcloud or one of the apps require upgrade - only a limited number of commands are available
            Cannot write into "config" directory!
            installed: ''
        """
        # self.module.log(msg=f" rc : '{rc}'")
        # self.module.log(msg=f" out: '{out.strip()}'")
        # self.module.log(msg=f" err: '{err.strip()}'")

        if not check_installed:
            self.module.log(msg=f"= rc: {rc}, out: {out.strip()}, err: {err.strip()}")

            if rc == 0:
                pattern = re.compile(r"Nextcloud or one of the apps require upgrade.*", re.MULTILINE)
                need_upgrade = re.search(pattern, err)

                if need_upgrade:
                    out = "Nextcloud or one of the apps require upgrade.\nYou may use your browser or the occ upgrade command to do the upgrade."
                    rc = 1

            return rc, out, err

        installed = False

        if rc == 0:
            pattern = re.compile(r"Nextcloud or one of the apps require upgrade.*", re.MULTILINE)
            need_upgrade = re.search(pattern, err)

            # self.module.log(msg=f" out: '{need_upgrade}'")
            # self.module.log(msg=f" err: '{need_upgrade}' {type(need_upgrade)}")

            if need_upgrade:
                installed = False

                self.occ_upgrade()

            pattern = re.compile(r"Nextcloud is not installed.*", re.MULTILINE)
            # installed_out = re.search(pattern_1, out)
            is_installed = re.search(pattern, err)

            self.module.log(msg=f" out: '{is_installed}'")
            self.module.log(msg=f" err: '{is_installed}' {type(is_installed)}")

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

        self.module.log(msg=f"= rc: {rc}, installed: {installed}, out: {out.strip()}, err: {err.strip()}")

        return (rc, installed, out, err)

    def maintenance_install(self, config: dict):
        """
            sudo -u www-data php occ
                maintenance:install
                --database='mysql'
                --database-host=database
                --database-port=3306
                --database-name='nextcloud'
                --database-user='nextcloud'
                --database-pass='nextcloud'
                --admin-user='admin'
                --admin-pass='admin'
        """
        # self.module.log(f"Occ::maintenance_install({config})")

        _failed = True
        _changed = False

        database = config.get("database", {})
        admin = config.get("admin", {})

        # self.module.log(msg=f" database: '{database}'")
        # self.module.log(msg=f" admin   : '{admin}'")

        data_dir = config.get("data_dir", None)
        dba_type = database.get("type", None)
        dba_hostname = database.get("hostname", None)
        dba_port = database.get("port", None)
        dba_schema = database.get("schema", None)
        dba_username = database.get("username", None)
        dba_password = database.get("password", None)
        admin_username = admin.get("username", None)
        admin_password = admin.get("password", None)

        args = []
        args += self.occ_base_args

        args.append("maintenance:install")

        if data_dir:
            args.append("--data-dir")
            args.append(data_dir)

        args.append("--database")
        args.append(dba_type)

        if dba_type == "mysql":
            args.append("--database-host")
            args.append(dba_hostname)
            args.append("--database-port")
            args.append(dba_port)
            args.append("--database-name")
            args.append(dba_schema)
            args.append("--database-user")
            args.append(dba_username)
            args.append("--database-pass")
            args.append(dba_password)

        args.append("--admin-user")
        args.append(admin_username)
        args.append("--admin-pass")
        args.append(admin_password)
        args.append("--no-ansi")

        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            _msg = "database was successfully created."
            _failed = False
            _changed = True

            _config_file = os.path.join(self.working_dir, 'config', 'config.php')
            _config_backup = os.path.join(self.working_dir, 'config', 'config.bck')

            shutil.copyfile(_config_file, _config_backup)

            self.config_list()
        else:
            patterns = [
                '.*Command "maintenance:install" is not defined.*',
                'Database .* is not supported.',
                'Following symlinks is not allowed',
                'Username is invalid because files already exist for this user',
                'Login is invalid because files already exist for this user'
            ]
            error = None

            # self.module.log("--------------------")

            _output = []
            _output += out.splitlines()
            _output += err.splitlines()

            self.module.log(f" - {_output}")

            for pattern in patterns:
                filter_list = list(filter(lambda x: re.search(pattern, x), _output))
                if len(filter_list) > 0 and isinstance(filter_list, list):
                    error = (filter_list[0]).strip()
                    self.module.log(msg=f"  - {error}")

                    break
            # self.module.log("--------------------")

            _, installed, version, _, err = self.status()

            if rc == 0 and not error and installed:
                _failed = False
                _changed = False
                _msg = f"Nextcloud {version} already installed."
            else:

                # self.module.log(msg=f" error: {type(error)} - '{error}'")
                # self.module.log(msg=f" err  : {type(err)} - '{err}'")

                _failed = True
                _changed = False
                _msg = error

        return dict(
            failed=_failed,
            changed=_changed,
            msg=_msg
        )

    def background_job(self, crontype: str) -> dict:
        """
        """
        # self.module.log(f"Occ::background_job({crontype})")
        args = []
        args += self.occ_base_args

        args.append(f"background:{crontype}")
        args.append("--no-ansi")

        rc, out, err = self._exec(args, check_rc=False)

        return dict(
            failed=not (rc == 0),
            msg=out.strip()
        )

    def config_list(self, type: str = "system"):
        """
            sudo -u www-data php occ config:list system
        """
        # self.module.log(f"Occ::config_list({type})")

        args = []
        args += self.occ_base_args

        args.append("config:list")
        args.append("system")
        args.append("--no-ansi")

        # self.module.log(msg=f" args: '{args}'")

        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            file_name = self._occ = os.path.join(self.working_dir, 'config', 'config.json')

            with open(file_name, "w") as f:
                f.write(out)

        return dict(
            failed=False,
            changed=False,
        )

    def _exec(self, args: list, check_rc: bool = True):
        """
        """
        # self.module.log(msg=f"Occ::_exec({args}, {check_rc})")

        rc, out, err = self.module.run_command(args, cwd=self.working_dir, check_rc=check_rc)

        # self.module.log(msg=f"  rc : '{rc}'")
        # self.module.log(msg=f"  out: '{out.strip()}'")
        # self.module.log(msg=f"  err: '{err.strip()}'")
        # for line in err.splitlines():
        #     self.module.log(msg=f"   {line.strip()}")

        return rc, out, err
