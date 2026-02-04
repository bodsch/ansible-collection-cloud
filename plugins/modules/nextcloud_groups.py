#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

from typing import Any, Dict, List, Optional, TypedDict, cast

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.cloud.plugins.module_utils.nextcloud.identities import (
    NextcloudIdentity,
)
from ansible_collections.bodsch.core.plugins.module_utils.module_results import results

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: nextcloud_groups
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"
version_added: "1.0.0"

short_description: Manage Nextcloud groups via occ
description:
  - Manage Nextcloud groups using the Nextcloud C(occ) command.
  - Supports creating and removing groups.
  - Uses C(occ group:list) to determine existing groups and behave idempotently.

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
  groups:
    description:
      - List of groups to manage.
    type: list
    required: false
    default: []
    elements: dict
    suboptions:
      name:
        description:
          - Group id to manage.
        type: str
        required: true
      state:
        description:
          - Desired state of the group.
          - C(present) ensures the group exists.
          - Any other value is treated as removal (kept for backward compatibility of this module).
        type: str
        required: false
        default: present
      display_name:
        description:
          - Optional display name for the group when creating it.
        type: str
        required: false

notes:
  - Requires a working Nextcloud installation and permission to execute C(php occ) as the configured OS user.
  - For idempotence, this module queries existing groups and only creates/removes when needed.

"""

EXAMPLES = r"""
- name: Ensure groups are present
  nextcloud_groups:
    working_dir: /var/www/nextcloud
    owner: www-data
    groups:
      - name: editors
        state: present
        display_name: Editors
      - name: viewers
        state: present

- name: Remove a group
  nextcloud_groups:
    working_dir: /var/www/nextcloud
    owner: www-data
    groups:
      - name: deprecated
        state: absent
"""

RETURN = r"""
changed:
  description: Whether any group was changed (created or removed).
  type: bool
  returned: always
failed:
  description: Whether the module failed.
  type: bool
  returned: always
state:
  description:
    - Per-group results.
    - Each list element is a dict containing the group name as key and a result dict as value.
  type: list
  elements: dict
  returned: always
  sample:
    - editors:
        failed: false
        changed: true
        msg: "Group was successfully created."
    - deprecated:
        failed: false
        changed: false
        msg: "The group does not exist (anymore)."
"""


# ---------------------------------------------------------------------------------------


class ModuleGroupItem(TypedDict, total=False):
    name: str
    state: str
    display_name: Optional[str]


class NextcloudGroups(NextcloudIdentity):
    """ """

    module: AnsibleModule

    def __init__(self, module: AnsibleModule):
        """ """
        self.module = module

        params = cast(Dict[str, Any], module.params)

        self.groups: List[ModuleGroupItem] = params.get("groups") or []
        self.working_dir: str = cast(str, params.get("working_dir"))
        self.owner: str = cast(str, params.get("owner"))

        super().__init__(module, self.owner, self.working_dir)

    def run(self) -> Dict[str, Any]:
        """ """

        error, msg = self.self_check()

        if error:
            return cast(Dict[str, Any], msg)

        rc, installed, out, err = self.check(check_installed=True)

        if not installed and rc == 1:
            return dict(failed=False, changed=False, msg=out)

        # Keep cached group list for idempotence checks.
        self.existing_groups = self.list_groups()

        result_state: List[Dict[str, Any]] = []

        if self.groups:
            for group in self.groups:
                group_state = (group.get("state") or "present").strip()
                group_name = group.get("name", None)
                group_display_name = group.get("display_name", None)

                if not group_name:
                    # Preserve previous behavior: silently skip invalid entries.
                    continue

                res: Dict[str, Any] = {}

                if group_state == "present":
                    if group_name in self.existing_groups:
                        res[group_name] = dict(
                            changed=False, msg="The group has already been created."
                        )
                    else:
                        res[group_name] = self.create_group(
                            name=group_name, display_name=group_display_name
                        )
                else:
                    # Treat any non-"present" as removal (preserves original behavior).
                    if group_name in self.existing_groups:
                        res[group_name] = self.remove_group(name=group_name)
                    else:
                        res[group_name] = dict(
                            changed=False, msg="The group does not exist (anymore)."
                        )

                result_state.append(res)

        _state, _changed, _failed, state, changed, failed = results(
            self.module, result_state
        )

        # Preserve return shape: always failed=False at module level (as before).
        result = dict(changed=_changed, failed=False, state=result_state)

        return result


def main() -> None:
    """ """
    specs = dict(
        groups=dict(required=False, type=list, default=[]),
        working_dir=dict(required=True, type=str),
        owner=dict(required=False, type=str, default="www-data"),
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=False,
    )

    kc = NextcloudGroups(module)
    result = kc.run()

    module.log(msg=f"= result : '{result}'")

    module.exit_json(**result)


# import module snippets
if __name__ == "__main__":
    main()
