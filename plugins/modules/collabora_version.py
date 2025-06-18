#!/usr/bin/python3
# -*- coding: utf-8 -*-

# (c) 2022-2024, Bodo Schulz <bodo@boone-schulz.de>

from __future__ import absolute_import, print_function

import os
import re

from ansible.module_utils.basic import AnsibleModule

__metaclass__ = type


class CollaboraVersion(object):
    """
    """
    module = None

    def __init__(self, module):
        """
          Initialize all needed Variables
        """
        self.module = module
        self.soffice_bin = module.params.get("soffice_bin")

    def run(self):
        """ """
        result = dict(
            rc=127,
            failed=True,
            changed=False,
        )

        soffice_bin_exists = os.path.exists(self.soffice_bin)

        if not soffice_bin_exists:
            return dict(
                failed=True,
                msg="Collabora Office was not installed correctly."
            )

        else:

            args = [self.soffice_bin]
            args.append("--version")

            # self.module.log(msg=f" - args: {args}")

            rc, out, err = self._exec(command=args, check_rc=False)

            # self.module.log(msg=f"  out: '{out}'")
            # self.module.log(msg=f"  err: '{err}'")

            if rc != 0:
                return dict(
                    failed=True,
                    msg=f"{out} / {err}"
                )

            version_string = "unknown"

            # Collabora Office 24.04.6.1 cd7968a4dd2965f3e44fa29f528007aa4a54dc97
            pattern = re.compile(r"Collabora Office (?P<version>\d.*) .*")

            version = re.search(pattern, out)

            if version:
                version_string = version.group('version')

            result['rc'] = rc

            if rc == 0:
                result['failed'] = False
                result['version'] = version_string

        return result

    def _exec(self, command, check_rc=True):
        """
          execute commands
        """
        rc, out, err = self.module.run_command(command, check_rc=check_rc)
        # self.module.log(msg=f"  rc : '{rc}'")

        if rc != 0:
            self.module.log(msg=f"  out: '{out}'")
            self.module.log(msg=f"  err: '{err}'")

        return rc, out, err


def main():
    """ """
    specs = dict(
        soffice_bin=dict(
            required=False,
            type='str',
            default="/opt/collaboraoffice/program/soffice.bin"
        ),

    )
    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=False,
    )

    helper = CollaboraVersion(module)
    result = helper.run()

    module.log(msg=f"= result: {result}")

    module.exit_json(**result)


# import module snippets
if __name__ == '__main__':
    main()
