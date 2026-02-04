#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

from typing import Any, Dict, Optional, TypedDict, cast

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.cloud.plugins.module_utils.nextcloud.config import (
    NextcloudConfig,
)
from ansible_collections.bodsch.core.plugins.module_utils.directory import (
    create_directory,
)

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: nextcloud_config
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"
version_added: "1.0.0"

short_description: Manage Nextcloud system configuration via occ config:import
description:
  - Applies Nextcloud system configuration using the Nextcloud C(occ) command.
  - Builds a JSON config payload and imports it via C(occ config:import).
  - Detects changes by comparing a generated JSON snapshot to the last applied snapshot.
  - Optionally generates a side-by-side diff of the configuration changes.

options:
  working_dir:
    description:
      - Path to the Nextcloud installation directory that contains the C(occ) script.
    type: str
    required: true
  owner:
    description:
      - OS user used to execute C(occ) and to fix ownership on config files.
    type: str
    required: false
    default: www-data
  group:
    description:
      - OS group used to fix ownership on config files.
    type: str
    required: false
    default: www-data
  trusted_domains:
    description:
      - Nextcloud trusted domains list (maps to C(trusted_domains) in Nextcloud system config).
    type: list
    elements: str
    required: false
  config_parameters:
    description:
      - Dictionary of Nextcloud system configuration parameters.
      - This is a structured object interpreted by the module utilities (e.g. language, locale, mail, proxy, logging, caching).
      - Unknown keys are ignored by the underlying implementation.
    type: dict
    required: false
  database:
    description:
      - Database related configuration overrides (e.g. MySQL utf8mb4/collation, dbuser/dbpassword/dbhost/dbname).
      - Structure is interpreted by the module utilities.
    type: dict
    required: false
  diff_output:
    description:
      - If enabled, return a side-by-side diff when changes are applied.
    type: bool
    required: false
    default: false
notes:
  - The module stores a snapshot file C(config/ansible.json) under the Nextcloud working directory to detect changes.
  - A backup of C(config/config.php) may be created during updates and restored if validation fails.
"""

EXAMPLES = r"""
- name: Configure Nextcloud trusted domains and basic settings
  nextcloud_config:
    working_dir: /var/www/nextcloud
    owner: www-data
    group: www-data
    trusted_domains:
      - cloud.example.com
      - cloud.internal.lan
    diff_output: true
    config_parameters:
      language:
        default: en
      locale:
        default: en_US
      phone_region: US
      theme: mytheme
      logging:
        type: file
        file: /var/log/nextcloud/nextcloud.log
        level: 2

- name: Configure mail settings
  nextcloud_config:
    working_dir: /var/www/nextcloud
    owner: www-data
    group: www-data
    config_parameters:
      mail:
        domain: example.com
        from_address: nextcloud
        mode: smtp
        hostname: smtp.example.com
        port: 587
        secure: tls
        auth:
          enabled: true
          username: smtp-user
          password: "super-secret"

- name: Configure database-related overrides (example)
  nextcloud_config:
    working_dir: /var/www/nextcloud
    owner: www-data
    group: www-data
    database:
      type: mysql
      username: nextcloud
      password: "db-secret"
      hostname: 127.0.0.1
      port: "3306"
      schema: nextcloud
      mysql:
        utf8mb4: true
        collation: utf8mb4_general_ci
"""

RETURN = r"""
changed:
  description: Whether the configuration was changed and imported.
  type: bool
  returned: always
failed:
  description: Whether the module failed.
  type: bool
  returned: always
msg:
  description: Human-readable summary message.
  type: str
  returned: always
diff:
  description:
    - Side-by-side diff output when C(diff_output=true) and changes occurred.
    - The exact format depends on the diff utility implementation (often a list of lines).
  type: raw
  returned: when supported
"""


# ---------------------------------------------------------------------------------------


class NextcloudConfigParams(TypedDict, total=False):
    owner: str
    group: str
    config_parameters: Dict[str, Any]
    trusted_domains: list
    database: Dict[str, Any]
    diff_output: bool


class NextcloudClient(NextcloudConfig):
    """ """

    module: AnsibleModule

    def __init__(self, module: AnsibleModule):
        """ """
        self.module = module

        params = cast(Dict[str, Any], module.params)

        # self._occ = module.get_bin_path('console', False)

        self.working_dir = cast(str, params.get("working_dir"))
        # self.data_dir = module.params.get("data_dir")
        self.owner = cast(str, params.get("owner"))
        self.group = cast(str, params.get("group"))
        self.config_parameters = cast(
            Optional[Dict[str, Any]], params.get("config_parameters")
        )
        self.trusted_domains = cast(Optional[list], params.get("trusted_domains"))
        self.database = cast(Optional[Dict[str, Any]], params.get("database"))
        self.diff_output = cast(bool, params.get("diff_output"))

        self.cache_directory = "/var/cache/ansible/nextcloud"

        super().__init__(
            module,
            owner=self.owner,
            working_dir=self.working_dir,
            cache_directory=self.cache_directory,
        )

        # NOTE: tmp_directory is already set by NextcloudConfig.__init__ using the current PID.
        # Keeping it in the base class avoids duplication and prevents accidental divergence.

    def run(self) -> Dict[str, Any]:
        """ """
        create_directory(directory=self.tmp_directory, mode="0750")
        create_directory(directory=self.cache_directory, mode="0750")

        error, msg = self.self_check()

        if error:
            return cast(Dict[str, Any], msg)

        rc, installed, out, err = self.check(check_installed=True)

        if not installed and rc == 1:
            return dict(failed=False, changed=False, msg=out)

        _config: NextcloudConfigParams = dict(
            owner=self.owner,
            group=self.group,
            config_parameters=self.config_parameters or {},
            trusted_domains=self.trusted_domains or [],
            database=self.database or {},
            diff_output=bool(self.diff_output),
        )

        result = self.check_config(params=_config)

        return cast(Dict[str, Any], result)


def main() -> None:
    """ """
    specs = dict(
        working_dir=dict(required=True, type=str),
        # data_dir=dict(
        #     required=False,
        #     type=str
        # ),
        owner=dict(required=False, type=str, default="www-data"),
        group=dict(required=False, type=str, default="www-data"),
        config_parameters=dict(
            required=False,
            type=dict,
        ),
        trusted_domains=dict(
            required=False,
            type=list,
        ),
        database=dict(required=False, type=dict),
        diff_output=dict(required=False, type="bool", default=False),
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=False,
    )

    kc = NextcloudClient(module)
    result = kc.run()

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
