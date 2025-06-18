#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.bodsch.cloud.plugins.module_utils.nextcloud.apps import NextcloudApps
from ansible_collections.bodsch.core.plugins.module_utils.module_results import results

__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'community'
}


class NextcloudApps(NextcloudApps):
    """
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        self.state = module.params.get("state")
        self.working_dir = module.params.get("working_dir")
        self.owner = module.params.get("owner")

        super().__init__(module, self.owner, self.working_dir)  # Ruft den Konstruktor der Basisklasse Occ auf

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

        rc, update, applications, err = self.check_for_updates()

        if self.state == "check":
            return dict(
                changed=False,
                updates=update,
                applications=applications
            )
        else:
            """
            """
            result_state = []
            res = {}

            for app, version in applications.items():
                self.module.log(f"  - {app} : {version}")

                state = self.update_app(app)

                if rc == 0:
                    res[app] = dict(
                        failed=False,
                        changed=True,
                        msg=f"successfully updated to version {version}."
                    )
                else:
                    res[app] = dict(
                        failed=True,
                        changed=False,
                        msg=f"update to version {version} failed."
                    )

                result_state.append(res)

            _state, _changed, _failed, state, changed, failed = results(self.module, result_state)

            result = dict(
                changed=_changed,
                failed=failed,
                state=result_state
            )

            return result

#         # ----
#
#         self._occ = os.path.join(self.working_dir, 'occ')
#
#         if not os.path.exists(self._occ):
#             return dict(
#                 failed=True,
#                 changed=False,
#                 msg="missing occ"
#             )
#
#         os.chdir(self.working_dir)
#
#         rc, installed, out, err = self.occ_check(check_installed=True)
#
#         if not installed and rc == 1:
#             return dict(
#                 failed=False,
#                 changed=False,
#                 msg=out
#             )
#
#         rc, update, applications, err = self.occ_check_for_updates()
#
#         if self.state == "check":
#             return dict(
#                 changed=False,
#                 updates=update,
#                 applications=applications
#             )
#         else:
#             """
#             """
#             result_state = []
#             res = {}
#
#             for app, version in applications.items():
#                 self.module.log(f"  - {app} : {version}")
#
#                 state = self.occ_update_app(app)
#
#                 if rc == 0:
#                     res[app] = dict(
#                         failed=False,
#                         changed=True,
#                         msg=f"successfully updated to version {version}."
#                     )
#                 else:
#                     res[app] = dict(
#                         failed=True,
#                         changed=False,
#                         msg=f"update to version {version} failed."
#                     )
#
#                 result_state.append(res)
#
#             _state, _changed, _failed, state, changed, failed = results(self.module, result_state)
#
#             result = dict(
#                 changed=_changed,
#                 failed=failed,
#                 state=result_state
#             )
#
#             return result
#
#     def occ_check(self, check_installed=False):
#         """
#             sudo -u www-data php occ check
#         """
#         # self.module.log(msg=f"occ_check({check_installed})")
#
#         args = []
#         args += self.occ_base_args
#
#         args.append("check")
#         args.append("--no-ansi")
#         args.append("--output")
#         args.append("json")
#
#         rc, out, err = self.__exec(args, check_rc=False)
#
#         """
#             not installed: "Nextcloud is not installed - only a limited number of commands are available"
#             installed: ''
#         """
#
#         if not check_installed:
#             return rc, out, err
#
#         installed = False
#
#         if rc == 0:
#             pattern = re.compile(r"Nextcloud is not installed.*", re.MULTILINE)
#             is_installed = re.search(pattern, err)
#
#             if is_installed:
#                 installed = False
#             else:
#                 installed = True
#
#         else:
#             err = out.strip()
#
#             pattern = re.compile(r"An unhandled exception has been thrown:\n(?P<exception>.*)\n.*", re.MULTILINE)
#             exception = re.search(pattern, err)
#
#             if exception:
#                 err = exception.user("exception")
#
#         return (rc, installed, out, err)
#
#     def occ_check_for_updates(self, check_installed=False):
#         """
#         """
#         self.module.log(msg=f"occ_check_for_updates({check_installed})")
#
#         app_names = []
#         res = dict()
#         update = False
#         args = []
#         args += self.occ_base_args
#
#         args.append("update:check")
#         args.append("--no-ansi")
#
#         rc, out, err = self.__exec(args, check_rc=False)
#
#         # self.module.log(msg=f"rc: {rc}, out: {out.strip()}, err: {err.strip()}")
#         # self.module.log(msg=f"  {len(out)}")
#         # self.module.log(msg=f"  {len(err)}")
#
#         if rc == 0:
#             pattern = re.compile(r"Update for (?P<app>.*) to version (?P<version>.*) is available.*", flags=re.MULTILINE)  # | re.DOTALL)
#
#             for match in pattern.finditer(out):
#                 # self.module.log(f"match : {match}")
#                 app, version = match.groups()
#                 # self.module.log(f"  - {app} : {version}")
#                 res.update({app: version})
#
#         update = len(res) >= 1
#
#         # self.module.log(msg=f"= (rc: {rc}, update: {update}, out: {res}, err: {err})")
#
#         return (rc, update, res, err)
#
#     def occ_path_app(self, app_name):
#         """
#         """
#         self.module.log(msg=f"occ_path_app({app_name})")
#         _failed = True
#         _changed = False
#
#         args = []
#         args += self.occ_base_args
#
#         args.append("app:getpath")
#         args.append("--no-ansi")
#         args.append(app_name)
#
#         rc, out, err = self.__exec(args, check_rc=False)
#
#         # self.module.log(msg=f"  out: '{out.strip()}')")
#         # self.module.log(msg=f"  err: '{err.strip()}')")
#
#         if rc == 0:
#             _installed = True
#             _failed = False
#             _changed = True
#         else:
#             _installed = False
#             _failed = True
#             _changed = False
#
#         return (_failed, _changed, _installed)
#
#     def occ_update_app(self, app_name):
#         """
#         """
#         self.module.log(msg=f"occ_update_app({app_name})")
#         _failed = True
#         _changed = False
#         _msg = ""
#
#         args = []
#         args += self.occ_base_args
#
#         args.append("app:update")
#         args.append("--no-ansi")
#         args.append(app_name)
#
#         self.module.log(msg=f"args: {args}")
#
#         rc, out, err = self.__exec(args, check_rc=False)
#
#         return (rc, out, err)
#
#     def __exec(self, commands, check_rc=True):
#         """
#         """
#         rc, out, err = self.module.run_command(
#             commands,
#             cwd=self.working_dir,
#             check_rc=check_rc)
#
#         # self.module.log(msg=f"  rc : '{rc}'")
#         if rc != 0:
#             self.module.log(msg=f"cmd: '{commands}'")
#             self.module.log(msg=f"  rc : '{rc}'")
#             self.module.log(msg=f"  out: '{out}'")
#             self.module.log(msg=f"  err: '{err}'")
#             for line in err.splitlines():
#                 self.module.log(msg=f"   {line}")
#
#         return rc, out, err


def main():
    """
    """
    specs = dict(
        state=dict(
            default="check",
            choices=[
                "check",
                "update"
            ],
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

    kc = NextcloudApps(module)
    result = kc.run()

    module.log(msg=f"= result : '{result}'")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()


"""
sudo --user www-data php occ app

      app:disable
      app:enable
      app:getpath
      app:install
      app:list
      app:remove
      app:update

      config:app:delete
      config:app:get
      config:app:set
      files:scan-app-data
      integrity:check-app
      integrity:sign-app
      user:add-app-password

"""
