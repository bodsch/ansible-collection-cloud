#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

from typing import Any, Dict, List, TypedDict

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.cloud.plugins.module_utils.nextcloud.apps import (
    NextcloudApps as NextcloudAppsHelper,
)
from ansible_collections.bodsch.core.plugins.module_utils.module_results import results

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: nextcloud_apps
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"
version_added: "1.0.0"

short_description: Manage Nextcloud apps via occ (install/enable/disable/remove/configure)
description:
  - Manage Nextcloud apps using the Nextcloud C(occ) command.
  - Supports installing apps, enabling/disabling apps, removing apps, and applying app configuration via C(occ config:app:set).
  - App configuration is applied in an idempotent manner (reads current config where possible and sets only when needed).

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
  apps:
    description:
      - List of apps to manage.
    type: list
    required: false
    default: []
    elements: dict
    suboptions:
      name:
        description:
          - App identifier (e.g. C(calendar), C(richdocuments)).
        type: str
        required: true
      state:
        description:
          - Desired state of the app.
          - C(present) installs the app if needed (keeps it disabled unless already enabled elsewhere).
          - C(enabled) ensures the app is installed and enabled.
          - C(disabled) disables the app if installed/enabled.
          - C(absent) removes the app if installed.
        type: str
        required: false
        default: present
        choices:
          - present
          - enabled
          - disabled
          - absent
      settings:
        description:
          - App-specific configuration values.
          - Each key is written using C(occ config:app:set). Boolean values are typically mapped to C(yes)/C(no).
        type: dict
        required: false
        default: {}
notes:
  - This module requires a working Nextcloud installation and the ability to run C(php occ) as the configured OS user.
  - Environment preservation for sensitive values is handled by the underlying helper classes; avoid enabling verbose logging in production.

"""

EXAMPLES = r"""
- name: Install an app (keep disabled)
  nextcloud_apps:
    working_dir: /var/www/nextcloud
    owner: www-data
    apps:
      - name: calendar
        state: present

- name: Install and enable an app
  nextcloud_apps:
    working_dir: /var/www/nextcloud
    owner: www-data
    apps:
      - name: richdocuments
        state: enabled

- name: Configure an app (idempotent)
  nextcloud_apps:
    working_dir: /var/www/nextcloud
    owner: www-data
    apps:
      - name: richdocuments
        state: enabled
        settings:
          disable_certificate_verification: true
          # Example string value:
          wopi_url: "https://collabora.example.com"

- name: Disable an app
  nextcloud_apps:
    working_dir: /var/www/nextcloud
    owner: www-data
    apps:
      - name: calendar
        state: disabled

- name: Remove an app
  nextcloud_apps:
    working_dir: /var/www/nextcloud
    owner: www-data
    apps:
      - name: calendar
        state: absent
"""

RETURN = r"""
changed:
  description: Whether any app was changed (installed/enabled/disabled/removed/configured).
  type: bool
  returned: always
failed:
  description: Whether the module failed.
  type: bool
  returned: always
state:
  description:
    - Per-app results.
    - Each list element is a dict containing the app name as key and a result dict as value.
  type: list
  elements: dict
  returned: always
  sample:
    - calendar:
        failed: false
        changed: true
        msg: "App was successfully installed and enabled."
    - richdocuments:
        failed: false
        changed: false
        msg: "No changes required."
"""


# ---------------------------------------------------------------------------------------


class ModuleAppItem(TypedDict, total=False):
    name: str
    state: str
    settings: Dict[str, Any]


class NextcloudApps(NextcloudAppsHelper):
    """ """

    module: AnsibleModule

    def __init__(self, module: AnsibleModule):
        """ """
        self.module = module

        self.apps: List[ModuleAppItem] = module.params.get("apps") or []
        self.working_dir: str = module.params.get("working_dir")
        self.owner: str = module.params.get("owner")

        super().__init__(
            module, self.owner, self.working_dir
        )  # Ruft den Konstruktor der Basisklasse Occ auf

    @staticmethod
    def _as_str_list(value: Any) -> List[str]:
        """
        Coerce a value into a list[str] in a safe way.
        """
        if value is None:
            return []
        if isinstance(value, list):
            return [str(x) for x in value]
        return [str(value)]

    def run(self):
        """ """
        error, msg = self.self_check()

        if error:
            return msg

        # Keep call for compatibility/side effects, even if not used further.
        _rc, _installed, _out, _err = self.check(check_installed=True)

        existing_apps, enabled_apps, disabled_apps = self.list_apps()

        # Turn lists into sets for fast membership checks.
        enabled_set = set(enabled_apps)
        disabled_set = set(disabled_apps)

        result_state: List[Dict[str, Any]] = []

        if self.apps:
            for app in self.apps:
                """ """
                app_state = (app.get("state") or "present").strip()
                app_name = app.get("name", None)
                app_settings = app.get("settings", {}) or {}

                # Preserve previous behavior: groups is currently always empty.
                groups: List[str] = []

                if not app_name:
                    # Keep same behavior as previous code (silently skip).
                    continue

                res: Dict[str, Any] = {}

                _, _, installed = self.path_app(app_name=app_name)

                if app_state in ["present", "enabled"]:
                    install_app: Dict[str, Any] = {}
                    enabled_app: Dict[str, Any] = {}
                    config_app: Dict[str, Any] = {}

                    if not installed:
                        install_app = self.install_app(app_name=app_name)
                    else:
                        res[app_name] = dict(
                            changed=False, msg="The app has already been installed."
                        )

                    # Enable application (only if requested and needed)
                    should_enable = (
                        app_state == "enabled"
                        and (app_name in disabled_set or not installed)
                        and not install_app.get("failed", False)
                    )
                    if should_enable:
                        enabled_app = self.enable_app(app_name=app_name, groups=groups)

                    # Configure application (idempotent logic lives in helper app_settings())
                    if isinstance(app_settings, dict) and len(app_settings) > 0:
                        config_app = self.app_settings(
                            app_name=app_name, app_settings=app_settings
                        )

                    failed = bool(
                        install_app.get("failed", False)
                        or enabled_app.get("failed", False)
                    )
                    changed = bool(
                        install_app.get("changed", False)
                        or enabled_app.get("changed", False)
                        or config_app.get("changed", False)
                    )

                    install_msg = str(install_app.get("msg", "") or "")
                    enabled_msg = str(enabled_app.get("msg", "") or "")
                    config_msg = config_app.get("msg", "")

                    # Preserve previous msg behavior but include config-only changes.
                    msg_out = ""
                    if failed:
                        if install_msg:
                            msg_out = install_msg
                        if enabled_msg:
                            msg_out += f"{enabled_msg}"
                        if not msg_out and config_msg:
                            msg_out = str(config_msg)
                    else:
                        if install_msg and enabled_msg:
                            msg_out = "App was successfully installed and enabled."
                        elif install_msg and not enabled_msg:
                            msg_out = install_msg
                        elif not install_msg and enabled_msg:
                            msg_out = enabled_msg
                        elif not install_msg and not enabled_msg and config_msg:
                            msg_out = str(config_msg)

                    # Ensure stable return shape per app: always a dict with at least changed/msg and failed when relevant.
                    res[app_name] = dict(
                        failed=failed,
                        changed=changed,
                        state=(
                            msg_out
                            if msg_out
                            else ("No changes required." if not changed else "Updated.")
                        ),
                    )

                elif app_state in ["absent", "disabled"]:
                    if app_state == "disabled" and (
                        app_name in enabled_set or installed
                    ):
                        res[app_name] = self.disable_app(app_name=app_name)

                    if app_state == "absent":
                        if app_name in enabled_set or app_name in disabled_set:
                            res[app_name] = self.remove_app(app_name=app_name)
                        else:
                            res[app_name] = dict(
                                changed=False, msg="The app was not installed."
                            )

                result_state.append(res)

        # filter empty dictionaries
        result_state = [item for item in result_state if item]
        # rename key
        # result_state = rename_key(result_state, "msg", "state")

        has_state, has_changed, has_failed, state, changed, failed = results(
            self.module, result_state
        )

        result = dict(changed=has_changed, failed=has_failed, state=result_state)

        return result


def rename_key(data: Any, old_key: str, new_key: str) -> Any:
    """
    Recursively rename dictionary keys inside nested structures.

    Args:
        data:
            Arbitrary nested structure consisting of dicts/lists.
        old_key:
            Key to replace.
        new_key:
            Replacement key.

    Returns:
        Modified structure with renamed keys.
    """

    if isinstance(data, dict):
        return {
            (new_key if key == old_key else key): rename_key(value, old_key, new_key)
            for key, value in data.items()
        }

    if isinstance(data, list):
        return [rename_key(item, old_key, new_key) for item in data]

    return data


def main():
    """ """
    specs = dict(
        apps=dict(required=False, type=list, default=[]),
        working_dir=dict(required=True, type=str),
        owner=dict(required=False, type=str, default="www-data"),
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=False,
    )

    kc = NextcloudApps(module)
    result = kc.run()

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
