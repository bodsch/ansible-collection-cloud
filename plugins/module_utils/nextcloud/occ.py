#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2021, Bodo Schulz <bodo@boone-schulz.de>
# BSD 2-clause (see LICENSE or https://opensource.org/licenses/BSD-2-Clause)

from __future__ import absolute_import, print_function
import os
import re
import shutil


class Occ(object):
    """
    """
    module = None

    def __init__(self, module):
        """
        """
        self.module = module

        self.occ_base_args = [
            "sudo",
            "--user",
            self.owner,
            "php",
            "occ"
        ]

    def status(self):
        """
        """
        self._occ = os.path.join(self.working_dir, 'occ')

        self.module.log(msg=f" console   : '{self._occ}'")

        if not os.path.exists(self._occ):
            return dict(
                failed = True,
                changed = False,
                msg = "missing occ"
            )

        self.module.log(msg=f" command   : '{self.command}'")
        self.module.log(msg=f" parameters: '{self.parameters}'")

        os.chdir(self.working_dir)

        version_string = None

        args = []
        args += self.occ_base_args

        args.append("status")
        args.append("--no-ansi")

        self.module.log(msg=f" args: '{args}'")

        rc, out, err = self.__exec(args, check_rc=False)

        if rc == 0:
            pattern = re.compile(r".*installed: (?P<installed>.*)\n.*version: (?P<version>.*)\n.*versionstring: (?P<versionstring>.*)\n.*edition: (?P<edition>.*)\n.*maintenance: (?P<maintenance>.*)\n.*needsDbUpgrade: (?P<db_upgrade>.*)\n.*productname: (?P<productname>.*)\n.*extendedSupport: (?P<extended_support>.*)", re.MULTILINE)
            version = re.search(pattern, out)

            if version:
                version_string = version.group('version')
        else:
            err = out.strip()

            pattern = re.compile(r"An unhandled exception has been thrown:\n(?P<exception>.*)\n.*", re.MULTILINE)
            exception = re.search(pattern, err)

            if exception:
                err = exception.group("exception")

        self.module.log(msg=f"  version     : {version_string}")

        return (rc == 0, version_string, err)
