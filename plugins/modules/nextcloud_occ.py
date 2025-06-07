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
import shutil

from ansible.module_utils.basic import AnsibleModule


__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'community'
}


class NextcloudClient(object):
    """
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        # self._occ = module.get_bin_path('console', False)

        self.command = module.params.get("command")
        self.parameters = module.params.get("parameters")
        self.working_dir = module.params.get("working_dir")
        self.data_dir = module.params.get("data_dir")
        self.owner = module.params.get("owner")
        self.database = module.params.get("database")
        self.admin = module.params.get("admin")

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

        if self.data_dir:
            current_owner, current_group, current_mode = self.__file_state(self.data_dir)
            # self.module.log(f" {self.data_dir} : {current_owner}:{current_group} : {current_mode}")

        if self.command == "check":
            rc, out, err = self.occ_check(check_installed=False)

            if int(rc) == 0:
                return dict(
                    failed=False,
                    msg=out
                )
            else:
                return dict(
                    failed=True,
                    msg=out.replace("<br/>", " ")
                )

        if self.command == "status":
            rc, installed, version_string, db_upgrade, err = self.occ_status()

            if db_upgrade:
                return dict(
                    failed=False,
                    upgrade=db_upgrade,
                    msg=f"Nextcloud is in Version {version_string} installed, but need an Database upgrade."
                )

            if int(rc) == 0:
                return dict(
                    failed=False,
                    upgrade=db_upgrade,
                    msg=err
                )
            else:
                return dict(
                    failed=True,
                    upgrade=db_upgrade,
                    msg=err.replace("<br/>", " ")
                )

        if self.command == "upgrade":
            rc, out, err = self.occ_upgrade()

            if int(rc) == 0:
                return dict(
                    failed=False,
                    msg=err
                )
            else:
                return dict(
                    failed=True,
                    msg=err.replace("<br/>", " ")
                )

        if self.command == "maintenance:install":
            rc, installed, out, err = self.occ_check(check_installed=True)
            if rc == 0 and not installed:
                result_install = self.occ_maintenance_install()
                result_status = self.occ_status()
                self.module.log(f" status: {result_status}")

                return result_install

            else:
                return dict(
                    failed=False,
                    changed=False,
                    msg=out
                )

        if self.command.startswith("background"):
            _, crontype = self.command.split(":")

            if crontype in ["ajax", "cron", "webcron"]:
                return self.occ_background_job(crontype)

    def occ_check(self, check_installed=False):
        """
            sudo -u www-data php occ check
        """
        self.module.log(msg=f"occ_check(check_installed={check_installed})")

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

    def occ_upgrade(self):
        """
            db:add-missing-columns                 Add missing optional columns to the database tables
            db:add-missing-indices                 Add missing indices to the database tables
            db:add-missing-primary-keys
        """
        self.module.log(msg="occ_upgrade()")

        args = []
        args += self.occ_base_args

        args.append("upgrade")
        args.append("--no-ansi")
        # args.append("--output")
        # args.append("json")

        self.module.log(msg=f" args: '{args}'")

        rc, out, err = self.__exec(args, check_rc=False)

        self.module.log(msg=f" rc : '{rc}'")
        self.module.log(msg=f" out: '{out.strip()}'")
        self.module.log(msg=f" err: '{err.strip()}'")

        if rc == 0:
            self.module.log(msg="okay?")

            err = "The upgrade was successful."

        else:
            err = out.strip()

            pattern = re.compile(r"An unhandled exception has been thrown:\n(?P<exception>.*)\n.*", re.MULTILINE)
            exception = re.search(pattern, err)

            if exception:
                err = exception.group("exception")

        self.module.log(msg=f"= rc: {rc}, out: {out.strip()}, err: {err.strip()}")
        return (rc, out, err)

    def occ_status(self):
        """
            sudo -u www-data php occ status
        """
        # self.module.log(msg="occ_status()")
        installed = False
        version_string = None

        args = []
        args += self.occ_base_args

        args.append("status")
        args.append("--no-ansi")
        args.append("--output")
        args.append("json")

        self.module.log(msg=f" args: '{args}'")

        rc, out, err = self.__exec(args, check_rc=False)

        self.module.log(msg=f" rc : '{rc}'")
        self.module.log(msg=f" out: '{out.strip()}'")
        self.module.log(msg=f" err: '{err.strip()}'")

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

    def occ_maintenance_install(self):
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
        self.module.log(msg="occ_maintenance_install()")
        _failed = True
        _changed = False

        # self.module.log(msg=f" database: '{self.database}'")
        # self.module.log(msg=f" admin   : '{self.admin}'")

        dba_type = self.database.get("type", None)
        dba_hostname = self.database.get("hostname", None)
        dba_port = self.database.get("port", None)
        dba_schema = self.database.get("schema", None)
        dba_username = self.database.get("username", None)
        dba_password = self.database.get("password", None)
        admin_username = self.admin.get("username", None)
        admin_password = self.admin.get("password", None)

        args = []
        args += self.occ_base_args

        args.append("maintenance:install")

        if self.data_dir:
            args.append("--data-dir")
            args.append(self.data_dir)

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

        rc, out, err = self.__exec(args, check_rc=False)

        if rc == 0:
            _msg = "database was successfully created."
            _failed = False
            _changed = True

            _config_file = os.path.join(self.working_dir, 'config', 'config.php')
            _config_backup = os.path.join(self.working_dir, 'config', 'config.bck')

            shutil.copyfile(_config_file, _config_backup)

            self.occ_config_list()
        else:
            patterns = [
                '.*Command "maintenance:install" is not defined.*',
                'Database .* is not supported.',
                'Following symlinks is not allowed',
                'Username is invalid because files already exist for this user'
            ]
            error = None

            for pattern in patterns:
                filter_list = list(filter(lambda x: re.search(pattern, x), err.splitlines()))
                if len(filter_list) > 0 and isinstance(filter_list, list):
                    error = (filter_list[0]).strip()
                    # self.module.log(msg=f"  - {error}")
                    break
            # self.module.log("--------------------")

            _, installed, version, err = self.occ_status()

            if rc == 0 and not error and installed:
                _failed = False
                _changed = False
                _msg = f"Nextcloud {version} already installed."
            else:

                # self.module.log(msg=f" error: {type(error)} - '{error}'")
                # self.module.log(msg=f" err  : {type(err)} - '{err}'")

                _failed = True
                _changed = False
                _msg = error  # " ".join([error, err])

        return dict(
            failed=_failed,
            changed=_changed,
            msg=_msg
        )

    def occ_config_list(self, type="system"):
        """
            sudo -u www-data php occ config:list system
        """

        args = []
        args += self.occ_base_args

        args.append("config:list")
        args.append("system")
        args.append("--no-ansi")

        # self.module.log(msg=f" args: '{args}'")

        rc, out, err = self.__exec(args, check_rc=False)

        if rc == 0:
            file_name = self._occ = os.path.join(self.working_dir, 'config', 'config.json')

            with open(file_name, "w") as f:
                f.write(out)

        return dict(
            failed=False,
            changed=False,
        )

    def occ_background_job(self, crontype):
        """
            https://docs.nextcloud.com/server/latest/admin_manual/configuration_server/occ_command.html#background-jobs-selector
        """
        args = []
        args += self.occ_base_args

        args.append(f"background:{crontype}")
        args.append("--no-ansi")

        rc, out, err = self.__exec(args, check_rc=False)

        return dict(
            failed=not (rc == 0),
            msg=out.strip()
        )

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
        command=dict(
            default="status",
            choices=[
                "status",
                "check",
                "upgrade",
                "maintenance:install",
                "background:ajax",
                "background:cron",
                "background:webcron"
            ]
        ),
        parameters=dict(
            required=False,
            type=list,
            default=[]
        ),
        working_dir=dict(
            required=True,
            type=str
        ),
        data_dir=dict(
            required=False,
            type=str
        ),
        owner=dict(
            required=False,
            type=str,
            default="www-data"
        ),
        database=dict(
            required=False,
            type=dict
        ),
        admin=dict(
            required=False,
            type=dict
        )
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=False,
    )

    kc = NextcloudClient(module)
    result = kc.run()

    module.log(msg=f"= result : '{result}'")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()


"""
sudo -u www-data php occ status

sudo -u www-data php occ  maintenance:install \
    --database='mysql' \
    --database-host=database \
    --database-port=3306 \
    --database-name='nextcloud' \
    --database-user='nextcloud' \
    --database-pass='nextcloud' \
    --admin-user='admin' \
    --admin-pass='admin'

sudo -u www-data php occ upgrade

# sudo -u www-data php occ config:list system
The current PHP memory limit is below the recommended value of 512MB.
{
    "system": {
        "passwordsalt": "***REMOVED SENSITIVE VALUE***",
        "secret": "***REMOVED SENSITIVE VALUE***",
        "trusted_domains": [
            "localhost"
        ],
        "datadirectory": "***REMOVED SENSITIVE VALUE***",
        "dbtype": "mysql",
        "version": "26.0.5.1",
        "overwrite.cli.url": "http://localhost",
        "dbname": "***REMOVED SENSITIVE VALUE***",
        "dbhost": "***REMOVED SENSITIVE VALUE***",
        "dbport": "",
        "dbtableprefix": "oc_",
        "mysql.utf8mb4": true,
        "dbuser": "***REMOVED SENSITIVE VALUE***",
        "dbpassword": "***REMOVED SENSITIVE VALUE***",
        "installed": true,
        "instanceid": "***REMOVED SENSITIVE VALUE***"
    }
}

# cat trusted_doamins.json  | jq
{
  "system": {
    "trusted_domains": [
      "owncloud.alpha.lab",
      "vm.alpha.lab"
    ]
  }
}

sudo -u www-data php occ config:import trusted_doamins.json


"""
