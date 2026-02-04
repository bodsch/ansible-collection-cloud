#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

from typing import Any, Dict, List, TypedDict, cast

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.cloud.plugins.module_utils.nextcloud.identities import (
    NextcloudIdentity,
)
from ansible_collections.bodsch.core.plugins.module_utils.module_results import results

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: nextcloud_users
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"
version_added: "1.0.0"

short_description: Manage Nextcloud users, groups membership, and user settings via occ
description:
  - Manage Nextcloud users using the Nextcloud C(occ) command.
  - Supports creating and deleting users, optionally resetting passwords, managing group membership, and applying user settings.
  - Uses C(occ user:list), C(occ group:list) and C(occ user:info) for idempotent decisions where possible.

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
  users:
    description:
      - List of users to manage.
    type: list
    required: false
    default: []
    elements: dict
    suboptions:
      name:
        description:
          - User id (uid) to manage.
        type: str
        required: true
      state:
        description:
          - Desired state of the user.
          - C(present) ensures the user exists.
          - Any other value triggers deletion in this module (commonly C(absent)).
        type: str
        required: false
        default: present
      password:
        description:
          - Password to set when creating a user, or when C(resetpassword=true).
          - Passed via environment variable C(OC_PASS) and C(--password-from-env).
        type: str
        required: false
      display_name:
        description:
          - Display name for the user at creation time.
        type: str
        required: false
      resetpassword:
        description:
          - If true and the user already exists, reset the user's password using the provided C(password).
        type: bool
        required: false
        default: false
      groups:
        description:
          - Desired group membership for the user.
          - The module will add missing groups and remove extra groups.
          - Non-existing groups are skipped.
        type: list
        elements: str
        required: false
        default: []
      settings:
        description:
          - Per-user settings applied via C(occ user:setting).
          - Expected as a list of app namespaces with key/value dictionaries.
        type: list
        required: false
        default: []
        elements: dict

notes:
  - Requires a working Nextcloud installation and permission to execute C(php occ) as the configured OS user.
  - Passwords are passed via environment variables; ensure your sudoers configuration preserves C(OC_PASS) if sudo is used.

"""

EXAMPLES = r"""
- name: Ensure a user exists
  nextcloud_users:
    working_dir: /var/www/nextcloud
    owner: www-data
    users:
      - name: alice
        state: present
        display_name: "Alice Example"
        password: "SuperSecret!"

- name: Reset user password (if already present)
  nextcloud_users:
    working_dir: /var/www/nextcloud
    owner: www-data
    users:
      - name: alice
        state: present
        resetpassword: true
        password: "NewSecret!"

- name: Enforce group membership
  nextcloud_users:
    working_dir: /var/www/nextcloud
    owner: www-data
    users:
      - name: alice
        state: present
        groups:
          - editors
          - viewers

- name: Apply user settings
  nextcloud_users:
    working_dir: /var/www/nextcloud
    owner: www-data
    users:
      - name: alice
        state: present
        settings:
          - settings:
              display_name: "Alice Example"
              email: "alice@example.com"

- name: Remove a user
  nextcloud_users:
    working_dir: /var/www/nextcloud
    owner: www-data
    users:
      - name: alice
        state: absent
"""

RETURN = r"""
changed:
  description: Whether any user was changed (created/removed/password reset/groups/settings).
  type: bool
  returned: always
failed:
  description: Whether the module failed.
  type: bool
  returned: always
state:
  description:
    - Per-user results.
    - Each list element is a dict containing the user id as key and a result dict as value.
  type: list
  elements: dict
  returned: always
  sample:
    - alice:
        failed: false
        changed: true
        msg: "User was successfully created."
"""


# ---------------------------------------------------------------------------------------


class ModuleUserItem(TypedDict, total=False):
    name: str
    state: str
    password: str
    display_name: str
    resetpassword: bool
    groups: List[str]
    settings: List[Dict[str, Any]]


class NextcloudUsers(NextcloudIdentity):
    """ """

    module: AnsibleModule

    def __init__(self, module: AnsibleModule):
        """ """
        self.module = module

        params = cast(Dict[str, Any], module.params)

        self.users: List[ModuleUserItem] = cast(
            List[ModuleUserItem], params.get("users") or []
        )
        self.working_dir: str = cast(str, params.get("working_dir"))
        self.owner: str = cast(str, params.get("owner") or "www-data")

        super().__init__(module, self.owner, self.working_dir)

    @staticmethod
    def _ensure_result_shape(res: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure a stable per-user result structure.
        """
        if "failed" not in res:
            res["failed"] = False
        if "changed" not in res:
            res["changed"] = False
        if "msg" not in res:
            res["msg"] = ""
        # Normalize types defensively
        res["failed"] = bool(res.get("failed", False))
        res["changed"] = bool(res.get("changed", False))
        res["msg"] = str(res.get("msg", "") or "")
        return res

    @staticmethod
    def _append_msg(res: Dict[str, Any], extra: str) -> None:
        """
        Append text to res['msg'] safely.
        """
        if not extra:
            return
        base = str(res.get("msg", "") or "")
        res["msg"] = f"{base}{extra}"

    @staticmethod
    def _merge_flags(
        res: Dict[str, Any], *, failed: bool = False, changed: bool = False
    ) -> None:
        """
        Merge boolean flags into an existing result dict.
        """
        res["failed"] = bool(res.get("failed", False) or failed)
        res["changed"] = bool(res.get("changed", False) or changed)

    @staticmethod
    def _as_str_list(value: Any) -> List[str]:
        """
        Coerce a value into list[str] safely.
        """
        if value is None:
            return []
        if isinstance(value, list):
            return [str(x) for x in value]
        return [str(value)]

    def run(self) -> Dict[str, Any]:
        """ """
        error, msg = self.self_check()

        if error:
            return cast(Dict[str, Any], msg)

        rc, installed, out, err = self.check(check_installed=True)

        if not installed and rc == 1:
            return dict(failed=False, changed=False, msg=out)

        (self.existing_users, self.existing_groups) = self.identities()

        result_state: List[Dict[str, Any]] = []

        if self.users:
            for user in self.users:
                """ """
                user_state = (user.get("state", "present") or "present").strip()
                user_name = user.get("name", None)
                resetpassword = bool(user.get("resetpassword", False))
                user_groups = self._as_str_list(user.get("groups", []))
                user_settings = cast(
                    List[Dict[str, Any]], user.get("settings", []) or []
                )

                if not user_name:
                    # Preserve original behavior: silently ignore invalid entries.
                    continue

                res: Dict[str, Any] = {}

                if user_state == "present":
                    if user_name in self.existing_users:
                        if resetpassword:
                            res[user_name] = self.reset_password(
                                user_data=cast(dict, user)
                            )
                        else:
                            res[user_name] = dict(
                                changed=False,
                                msg="The user has already been created.",
                            )
                    else:
                        res[user_name] = self.create_user(user_data=cast(dict, user))
                        # Keep cache consistent for subsequent items in the same run.
                        if not res[user_name].get("failed", False):
                            self.existing_users.append(user_name)

                    # Ensure stable structure before augmenting message/flags
                    res[user_name] = self._ensure_result_shape(res[user_name])

                    # Groups
                    _group_failed, _group_changed, _group_msg = self.user_groups(
                        username=user_name, groups=user_groups
                    )
                    # Keep previous behavior of appending message, but also reflect flags.
                    if _group_msg:
                        self._append_msg(res[user_name], _group_msg)
                    self._merge_flags(
                        res[user_name], failed=_group_failed, changed=_group_changed
                    )

                    # Settings (now returns meaningful aggregation from the optimized helper)
                    _settings_failed, _settings_changed, _settings_msg = (
                        self.user_settings(
                            username=user_name, user_settings=user_settings
                        )
                    )
                    if _settings_msg:
                        # Keep it readable; separate from previous message if needed.
                        sep = " " if res[user_name].get("msg") else ""
                        self._append_msg(res[user_name], f"{sep}{_settings_msg}")
                    self._merge_flags(
                        res[user_name],
                        failed=_settings_failed,
                        changed=_settings_changed,
                    )

                else:
                    if user_name in self.existing_users:
                        res[user_name] = self.remove_user(name=user_name)
                        # Keep cache consistent for subsequent items in the same run.
                        if not res[user_name].get("failed", False):
                            try:
                                self.existing_users.remove(user_name)
                            except ValueError:
                                pass
                    else:
                        res[user_name] = dict(
                            changed=False, msg="The user does not exist (anymore)."
                        )

                result_state.append(res)

        _state, _changed, _failed, state, changed, failed = results(
            self.module, result_state
        )

        # Preserve module-level return shape/behavior (failed stays False like before)
        result = dict(changed=_changed, failed=False, state=result_state)

        return cast(Dict[str, Any], result)


def main() -> None:
    """ """
    specs = dict(
        users=dict(required=False, type=list, default=[]),
        working_dir=dict(required=True, type=str),
        owner=dict(required=False, type=str, default="www-data"),
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=False,
    )

    kc = NextcloudUsers(module)
    result = kc.run()

    module.log(msg=f"= result : '{result}'")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
