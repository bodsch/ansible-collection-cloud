#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

from typing import Any, Dict, List, TypedDict, cast

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.cloud.plugins.module_utils.nextcloud.apps import (
    NextcloudApps as NextcloudAppsHelper,
)
from ansible_collections.bodsch.core.plugins.module_utils.module_results import results

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: nextcloud_update_apps
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"
version_added: "1.0.0"

short_description: Check for and apply Nextcloud app updates via occ
description:
  - Uses the Nextcloud C(occ) command to check for available app updates and optionally apply them.
  - In C(check) state it returns whether updates exist and a mapping of apps to available versions.
  - In C(update) state it updates all apps reported by C(occ update:check).

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
  state:
    description:
      - Whether to only check for updates or to apply updates.
    type: str
    required: false
    default: check
    choices:
      - check
      - update

notes:
  - Requires a working Nextcloud installation and permission to execute C(php occ) as the configured OS user.
  - Nextcloud may require maintenance mode and/or upgrades before app updates can be applied.

"""

EXAMPLES = r"""
- name: Check for available app updates
  nextcloud_update_apps:
    working_dir: /var/www/nextcloud
    owner: www-data
    state: check
  register: app_updates

- name: Print available updates
  ansible.builtin.debug:
    var: app_updates.applications

- name: Apply all available app updates
  nextcloud_update_apps:
    working_dir: /var/www/nextcloud
    owner: www-data
    state: update
"""

RETURN = r"""
changed:
  description:
    - In C(check) mode, always C(false).
    - In C(update) mode, whether any apps were updated.
  type: bool
  returned: always
failed:
  description:
    - Present in C(update) mode.
    - Whether updating apps failed.
  type: bool
  returned: when state=update
updates:
  description:
    - Present in C(check) mode.
    - Whether at least one update is available.
  type: bool
  returned: when state=check
applications:
  description:
    - Present in C(check) mode.
    - Mapping of app name to available target version.
  type: dict
  returned: when state=check
state:
  description:
    - Present in C(update) mode.
    - Per-app update results.
  type: list
  elements: dict
  returned: when state=update
  sample:
    - calendar:
        failed: false
        changed: true
        msg: "successfully updated to version 4.0.0."
"""


# ---------------------------------------------------------------------------------------


class ModuleParams(TypedDict, total=False):
    state: str
    working_dir: str
    owner: str


class NextcloudApps(NextcloudAppsHelper):
    """ """

    module: AnsibleModule

    def __init__(self, module: AnsibleModule):
        """ """
        self.module = module

        params = cast(Dict[str, Any], module.params)

        self.state: str = cast(str, params.get("state") or "check")
        self.working_dir: str = cast(str, params.get("working_dir"))
        self.owner: str = cast(str, params.get("owner") or "www-data")

        super().__init__(
            module, self.owner, self.working_dir
        )  # Ruft den Konstruktor der Basisklasse Occ auf

    def run(self) -> Dict[str, Any]:
        """ """
        error, msg = self.self_check()

        if error:
            return cast(Dict[str, Any], msg)

        rc_check, installed, out, err = self.check(check_installed=True)

        if not installed and rc_check == 1:
            return dict(failed=False, changed=False, msg=out)

        rc_updates, update, applications, err_updates = self.check_for_updates()

        if self.state == "check":
            return dict(changed=False, updates=update, applications=applications)

        # state == "update"
        if rc_updates != 0:
            # Keep return shape stable for update-mode: changed/failed/state
            return dict(
                changed=False,
                failed=True,
                state=[
                    {
                        "__all__": dict(
                            failed=True,
                            changed=False,
                            msg=(err_updates or "update:check failed").strip(),
                        )
                    }
                ],
            )

        if not applications:
            return dict(changed=False, failed=False, state=[])

        result_state: List[Dict[str, Any]] = []

        for app, version in applications.items():
            self.module.log(f"  - {app} : {version}")

            update_rc, _update_out, update_err = self.update_app(app)

            if update_rc == 0:
                res = {
                    app: dict(
                        failed=False,
                        changed=True,
                        msg=f"successfully updated to version {version}.",
                    )
                }
            else:
                res = {
                    app: dict(
                        failed=True,
                        changed=False,
                        msg=(
                            update_err.strip() or f"update to version {version} failed."
                        ),
                    )
                }

            result_state.append(res)

        _state, _changed, _failed, _state_detail, _changed_detail, failed = results(
            self.module, result_state
        )

        result = dict(changed=_changed, failed=failed, state=result_state)

        return result


def main() -> None:
    """ """
    specs = dict(
        state=dict(
            default="check",
            choices=["check", "update"],
        ),
        working_dir=dict(required=True, type=str),
        owner=dict(required=False, type=str, default="www-data"),
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=False,
    )

    kc = NextcloudApps(module)
    result = kc.run()

    module.log(msg=f"= result : '{result}'")

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
