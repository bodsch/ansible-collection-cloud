#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function
# import os
# import re
# import json
# import pwd
# import grp

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.cloud.plugins.module_utils.nextcloud.identities import NextcloudIdentity
from ansible_collections.bodsch.core.plugins.module_utils.module_results import results

__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'community'
}


class NextcloudUsers(NextcloudIdentity):
    """
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        self.users = module.params.get("users")
        self.working_dir = module.params.get("working_dir")
        self.owner = module.params.get("owner")

        super().__init__(module, self.owner, self.working_dir)

    def run(self):
        """
        """
        error, msg = self.self_check()

        if error:
            return msg

        rc, installed, out, err = self.check(check_installed=True)

        if not installed and rc == 1:
            return dict(
                failed=False,
                changed=False,
                msg=out
            )

        (self.existing_users, self.existing_groups) = self.identities()

        result_state = []

        if self.users:
            for user in self.users:
                """
                """
                # self.module.log(f" - {user}")

                user_state = user.get("state", "present")
                user_name = user.get("name", None)
                # user_password = user.get("password", None)
                resetpassword = user.get("resetpassword", None)
                # user_display_name = user.get("display_name", None)
                user_groups = user.get("groups", [])
                user_settings = user.get("settings", [])

                if user_name:
                    res = {}
                    if user_state == "present":

                        if user_name in self.existing_users:
                            if resetpassword:
                                res[user_name] = self.reset_password(user_data=user)
                            else:
                                res[user_name] = dict(
                                    changed=False,
                                    msg="The user has already been created."
                                )
                        else:
                            res[user_name] = self.create_user(user_data=user)

                        _group_failed, _group_changed, _group_msg = self.user_groups(username=user_name, groups=user_groups)

                        if not _group_failed and _group_changed:
                            res[user_name]["msg"] += _group_msg

                        _settings_failed, _settings_changed, _settings_msg = self.user_settings(username=user_name, user_settings=user_settings)

                    else:
                        if user_name in self.existing_users:
                            res[user_name] = self.remove_user(name=user_name)
                        else:
                            res[user_name] = dict(
                                changed=False,
                                msg="The user does not exist (anymore)."
                            )

                    result_state.append(res)

                else:
                    pass

        _state, _changed, _failed, state, changed, failed = results(self.module, result_state)

        result = dict(
            changed=_changed,
            failed=False,
            state=result_state
        )

        return result


def main():
    """
    """
    specs = dict(
        users=dict(
            required=False,
            type=list,
            default=[]
        ),
        working_dir=dict(
            required=True,
            type=str
        ),
        owner=dict(
            required=False,
            type=str,
            default="www-data"
        ),
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=False,
    )

    kc = NextcloudUsers(module)
    result = kc.run()

    module.log(msg=f"= result : '{result}'")

    module.exit_json(**result)


if __name__ == '__main__':
    main()


"""
sudo --user www-data php occ user

Did you mean one of these?
    group:adduser
    group:removeuser
    user:add
    user:add-app-password
    user:auth-tokens:add
    user:auth-tokens:delete
    user:auth-tokens:list
    user:delete
    user:disable
    user:enable
    user:info
    user:lastseen
    user:list
    user:report
    user:resetpassword
    user:setting
    user:sync-account-data

sudo --user www-data php occ user:list --output=json
sudo --user www-data php occ user:add --no-ansi --help
"""
