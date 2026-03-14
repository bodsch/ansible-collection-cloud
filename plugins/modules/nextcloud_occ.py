#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

from typing import Any, Dict, List, Optional, TypedDict, cast

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.cloud.plugins.module_utils.nextcloud.occ import Occ

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: nextcloud_occ
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"
version_added: "1.0.0"

short_description: Run common Nextcloud occ commands (check/status/upgrade/install/background)
description:
  - Provides a thin Ansible wrapper around the Nextcloud C(occ) CLI for common administrative tasks.
  - Supports running C(check), C(status), C(upgrade), C(maintenance:install), and background job configuration (ajax/cron/webcron).
  - Intended for orchestration and health/upgrade workflows.

options:
  working_dir:
    description:
      - Path to the Nextcloud installation directory that contains the C(occ) script.
    type: str
    required: true
  owner:
    description:
      - OS user used to execute C(occ) (typically C(www-data)).
    type: str
    required: false
    default: www-data
  command:
    description:
      - Operation to execute.
    type: str
    required: false
    default: status
    choices:
      - status
      - check
      - upgrade
      - maintenance:install
      - background:ajax
      - background:cron
      - background:webcron
  parameters:
    description:
      - Reserved for future use (currently not used by the module implementation).
    type: list
    required: false
    default: []
  data_dir:
    description:
      - Nextcloud data directory path, used by C(maintenance:install).
    type: str
    required: false
  database:
    description:
      - Database connection settings used by C(maintenance:install).
      - Structure depends on the underlying helper (type/hostname/port/schema/username/password).
    type: dict
    required: false
  admin:
    description:
      - Admin account settings used by C(maintenance:install).
      - Structure depends on the underlying helper (username/password).
    type: dict
    required: false

notes:
  - Requires a working Nextcloud installation and permission to execute C(php occ) as the configured OS user.
  - For C(maintenance:install), provide C(data_dir), C(database), and C(admin).

"""

EXAMPLES = r"""
- name: Check Nextcloud (simple)
  nextcloud_occ:
    working_dir: /var/www/nextcloud
    owner: www-data
    command: check

- name: Get Nextcloud status
  nextcloud_occ:
    working_dir: /var/www/nextcloud
    owner: www-data
    command: status
  register: nc_status

- name: Upgrade Nextcloud
  nextcloud_occ:
    working_dir: /var/www/nextcloud
    owner: www-data
    command: upgrade

- name: Install Nextcloud via maintenance:install
  nextcloud_occ:
    working_dir: /var/www/nextcloud
    owner: www-data
    command: maintenance:install
    data_dir: /var/lib/nextcloud/data
    database:
      type: mysql
      hostname: 127.0.0.1
      port: "3306"
      schema: nextcloud
      username: nextcloud
      password: "db-secret"
    admin:
      username: admin
      password: "admin-secret"

- name: Set background job mode to cron
  nextcloud_occ:
    working_dir: /var/www/nextcloud
    owner: www-data
    command: background:cron
"""

RETURN = r"""
failed:
  description: Whether the module failed.
  type: bool
  returned: always
msg:
  description: Human-readable result message from the selected operation.
  type: str
  returned: always
upgrade:
  description:
    - In C(status) mode, indicates whether a database upgrade is required.
    - In other modes, this key may be absent.
  type: bool
  returned: when command=status
rc:
  description:
    - Return code for unknown/unsupported operations.
    - The module returns C(rc=127) when the command is not recognized.
  type: int
  returned: when command is unsupported
changed:
  description:
    - Present for some operations such as C(maintenance:install) when no installation is performed.
    - Exact semantics depend on the command.
  type: bool
  returned: sometimes
"""


# ---------------------------------------------------------------------------------------


class DatabaseParams(TypedDict, total=False):
    type: str
    hostname: str
    port: str
    schema: str
    username: str
    password: str


class AdminParams(TypedDict, total=False):
    username: str
    password: str


class InstallConfig(TypedDict, total=False):
    data_dir: Optional[str]
    database: DatabaseParams
    admin: AdminParams


class NextcloudClient(Occ):
    """ """

    module: AnsibleModule

    def __init__(self, module: AnsibleModule):
        """ """
        self.module = module

        params = cast(Dict[str, Any], module.params)

        # self._occ = module.get_bin_path('console', False)

        self.command: str = cast(str, params.get("command"))
        self.parameters: List[Any] = cast(List[Any], params.get("parameters") or [])
        self.working_dir: str = cast(str, params.get("working_dir"))
        self.data_dir: Optional[str] = cast(Optional[str], params.get("data_dir"))
        self.owner: str = cast(str, params.get("owner") or "www-data")
        self.database: Dict[str, Any] = cast(
            Dict[str, Any], params.get("database") or {}
        )
        self.admin: Dict[str, Any] = cast(Dict[str, Any], params.get("admin") or {})

        super().__init__(module, self.owner, self.working_dir)

    @staticmethod
    def _clean_html(text: str) -> str:
        """
        Normalize Nextcloud/occ messages sometimes containing HTML line breaks.
        """
        return (text or "").replace("<br/>", " ").strip()

    def run(self) -> Dict[str, Any]:
        """ """
        error, msg = self.self_check()

        if error:
            return cast(Dict[str, Any], msg)

        if self.command == "check":
            rc, out, err = self.check(check_installed=False)

            if int(rc) == 0:
                return dict(failed=False, msg=out)

            if err:
                out += f"ERROR: {err}"

            return dict(failed=True, msg=self._clean_html(out))

        if self.command == "status":
            """ """
            rc, installed, version_string, db_upgrade, err = self.status()

            # self.module.log(f"  - {rc}")
            # self.module.log(f"  - {installed}")
            # self.module.log(f"  - {version_string}")
            # self.module.log(f"  - {db_upgrade}")
            # self.module.log(f"  - {err}")

            if db_upgrade:
                return dict(
                    failed=False,
                    upgrade=db_upgrade,
                    msg=f"Nextcloud is in Version {version_string} installed, but need an Database upgrade.",
                )

            if int(rc) == 0:
                return dict(failed=False, upgrade=db_upgrade, msg=err)

            return dict(failed=True, upgrade=db_upgrade, msg=self._clean_html(err))

        if self.command == "maintenance:install":
            rc, installed, out, err = self.check(check_installed=True)

            if rc == 0 and not installed:
                db = cast(DatabaseParams, self.database or {})
                adm = cast(AdminParams, self.admin or {})

                install_cfg: InstallConfig = dict(
                    data_dir=self.data_dir,
                    database=dict(
                        type=cast(str, db.get("type", None)),
                        hostname=cast(str, db.get("hostname", None)),
                        port=cast(str, db.get("port", None)),
                        schema=cast(str, db.get("schema", None)),
                        username=cast(str, db.get("username", None)),
                        password=cast(str, db.get("password", None)),
                    ),
                    admin=dict(
                        username=cast(str, adm.get("username", None)),
                        password=cast(str, adm.get("password", None)),
                    ),
                )

                result_install = self.maintenance_install(config=install_cfg)
                result_status = self.status()
                self.module.log(f" status: {result_status}")

                return cast(Dict[str, Any], result_install)

            return dict(failed=False, changed=False, msg=out)

        if self.command == "upgrade":
            rc, out, err = self.upgrade()

            if int(rc) == 0:
                return dict(failed=False, msg=err)
            return dict(failed=True, msg=self._clean_html(err))

        if self.command.startswith("background"):
            parts = self.command.split(":", 1)
            crontype = parts[1] if len(parts) == 2 else ""

            if crontype in ["ajax", "cron", "webcron"]:
                return cast(Dict[str, Any], self.background_job(crontype))

        return dict(rc=127, failed=True)


def main() -> None:
    """ """
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
                "background:webcron",
            ],
        ),
        parameters=dict(required=False, type=list, default=[]),
        working_dir=dict(required=True, type=str),
        data_dir=dict(required=False, type=str),
        owner=dict(required=False, type=str, default="www-data"),
        database=dict(required=False, type=dict),
        admin=dict(required=False, type=dict),
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
if __name__ == "__main__":
    main()
