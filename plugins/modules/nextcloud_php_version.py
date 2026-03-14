#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2022-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
Ansible module to discover available PHP package versions for the current Linux distribution.

The module inspects the package metadata of the host OS and returns an "available" version
structure containing:
- version: the discovered PHP version string (major.minor[.patch] depending on repository metadata)
- package_version: numeric package variant without dots (e.g. "82" for "8.2")
- major_version: the major version number (e.g. "8" for "8.2")

Supported platforms:
- Debian/Ubuntu: uses python-apt (python3-apt)
- Arch/Artix: uses pacman via Ansible's run_command

The module is read-only and does not modify system state.
"""

from __future__ import absolute_import, division, print_function

import re
from typing import Any, Dict, List, Optional, Tuple

from ansible.module_utils import distro
from ansible.module_utils.basic import AnsibleModule

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: php_version
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"
version_added: "1.0.0"

short_description: Discover the available PHP package version for the current distribution.
description:
  - Reads the system package metadata and determines a suitable PHP version string for the requested package.
  - On Debian/Ubuntu, this module requires C(python3-apt) to query APT metadata.
  - On Arch/Artix, this module calls C(pacman) to search repositories.

options:
  package:
    description:
      - The package name to inspect.
    type: str
    required: false
    default: php
  package_version:
    description:
      - Desired version prefix to match (e.g. C(8.2)).
      - If empty, the module returns the first version found in package metadata (typically the newest).
    type: str
    required: false
    default: ''

notes:
  - On Debian/Ubuntu, querying APT metadata requires a working local APT cache and python-apt.
  - This module does not install or update packages.
"""

EXAMPLES = r"""
- name: Discover default PHP version metadata (package=php)
  php_version:
  register: php_info

- name: Discover PHP 8.2 package version
  php_version:
    package: php
    package_version: "8.2"
  register: php82_info

- name: Discover php7 package on Arch/Artix (example)
  php_version:
    package: php7
    package_version: "7.4"
  register: php74_info

- name: Use results
  debug:
    msg:
      - "Version: {{ php_info.available.version }}"
      - "Major: {{ php_info.available.major_version }}"
      - "PkgVersion: {{ php_info.available.package_version }}"
"""

RETURN = r"""
available:
  description: Parsed version information.
  returned: always
  type: dict
  contains:
    version:
      description: The discovered PHP version string.
      type: str
      returned: always
    package_version:
      description: The version without dots (e.g. "82" for "8.2").
      type: str
      returned: always
    major_version:
      description: The major version (e.g. "8" for "8.2").
      type: str
      returned: always
msg:
  description: Additional information, especially on failure.
  returned: always
  type: str
failed:
  description: Whether the module failed.
  returned: always
  type: bool
"""

# ---------------------------------------------------------------------------------------

# PHP 8.5.3 (fpm-fcgi) (built: Feb 12 2026 16:29:14) (NTS)
_PHP_VERSION_RE = re.compile(r"^PHP (?P<version>.*?) ", re.MULTILINE)


class NextcloudPHPVersion:
    """
    Determine the available PHP package version for the current host distribution.

    The module supports:
    - Debian/Ubuntu via python-apt (APT cache inspection)
    - Arch/Artix via pacman search

    Public API stability:
    - __init__(module) keeps signature
    - run() returns a dict compatible with AnsibleModule.exit_json()/fail_json()
    """

    module: AnsibleModule

    def __init__(self, module: AnsibleModule):
        """
        Initialize the helper with AnsibleModule and compute distro information.

        Args:
            module: The AnsibleModule instance providing parameters and utilities.
        """
        self.module = module
        self.module.log("NextcloudPHPVersion::__init__()")

        self.php_package_name = module.params.get("package_name")
        self.php_package_version = module.params.get("package_version")

        self.php_legacy_binary = self.module.get_bin_path("php-legacy", False)
        self.php_binary = self.module.get_bin_path("php", False)

        self.distribution, self.version, self.codename = distro.linux_distribution(
            full_distribution_name=False
        )

    def run(self) -> Dict[str, Any]:
        """
        Execute the version discovery process.

        Returns:
            A result dictionary consumable by Ansible. Keys:
            - failed: bool
            - available: dict(version, package_version, major_version)
            - msg: str
        """
        self.module.log("NextcloudPHPVersion::run()")

        error = False
        version = ""

        version, error = self.php_version()

        if error:
            self.module.log(f"ERROR: {error}")
            return {"failed": True, "msg": error}

        result = dict(changed=False, failed=False, version=version)

        return result

    def php_version(self):
        """ """

        version: Dict[str] = {}
        error_msg: Optional[str] = None

        if self.php_legacy_binary:
            args = [self.php_legacy_binary]
        elif self.php_binary:
            args = [self.php_binary]
        else:
            return (None, "PHP does not appear to be installed in the default paths.")

        args += ["--version"]

        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            ver = _PHP_VERSION_RE.search(out)

            if ver:
                full_version = ver.group("version").strip()
                major_version = full_version.split(".", 1)[0]
                minor_version = full_version.split(".", 2)[1]

                version = {
                    "full_version": full_version,
                    "major_version": major_version,
                    "short_version": f"{major_version}.{minor_version}",
                }

            error_msg = None

        else:
            error_msg = err

        self.module.log(msg=f"{version}, {error_msg}")

        return version, error_msg

    def _exec(
        self,
        args: List[str],
        environ_update: Optional[Dict[str, str]] = None,
        check_rc: bool = True,
    ) -> Tuple[int, str, str]:
        """
        Execute a prepared command via the Ansible module's `run_command()`.

        Args:
            args: Full argument vector to execute (already includes `occ_base_args`).
            environ_update: Environment variables added/overridden for this process.
                Example: {"OC_PASS": "<secret>"} used together with `--password-from-env`.
            check_rc: If True, Ansible will raise a failure on non-zero return code.

        Returns:
            Tuple of (rc, out, err):
                - rc: return code (int)
                - out: stdout (str)
                - err: stderr (str)

        Security:
            Avoid logging secrets in `environ_update`. If you need debug logging, consider
            redacting sensitive keys before writing to module logs.
        """
        self.module.log(
            msg=f"NextcloudPHPVersion::_exec(args: {args}, environ_update: {environ_update}, check_rc: {check_rc})"
        )

        rc, out, err = self.module.run_command(
            args, environ_update=environ_update, check_rc=check_rc
        )

        # self.module.log(msg=f"  rc : '{rc}'")
        # self.module.log(msg=f"  out: '{out}'")
        # self.module.log(msg=f"  err: '{err}'")

        return rc, out, err


def main():
    """ """

    spec = dict(
        package_name=dict(
            required=False,
            default="php",
            type="str",
        ),
        package_version=dict(
            required=False,
            default="",
            type="str",
        ),
    )

    module = AnsibleModule(
        argument_spec=spec,
        supports_check_mode=False,
    )

    helper = NextcloudPHPVersion(module)
    result = helper.run()

    module.log(msg=f" = result : '{result}'")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
