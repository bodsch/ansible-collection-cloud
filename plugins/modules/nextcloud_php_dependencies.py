#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Ansible module for validating required PHP modules for Nextcloud.

The module inspects the available PHP extensions by executing ``php -m`` or
``php-legacy -m`` and compares the detected module list with a configured list
of required dependencies.

This module is read-only. It never modifies the target system and only reports
whether the requested PHP modules are available.
"""

# (c) 2026, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

from typing import Any, Dict, List, Optional, Sequence, Tuple, TypedDict, cast

from ansible.module_utils.basic import AnsibleModule

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: nextcloud_php_dependencies
short_description: Validate required PHP modules for Nextcloud
version_added: "1.0.0"

author:
  - Bodo Schulz (@bodsch) <bodo@boone-schulz.de>

description:
  - Validate whether the PHP modules required for a Nextcloud installation are
    available on the target host.
  - The module executes C(php -m) or C(php-legacy -m) and compares the detected
    module list with the required dependencies provided in O(php_dependencies).
  - The module is read-only and does not modify the target system.

options:
  package_name:
    description:
      - Preferred PHP package or binary family used to detect the runtime.
      - When set to C(php-legacy), the module prefers the C(php-legacy) binary.
      - For all other values, the module prefers the regular C(php) binary.
      - If the preferred binary is not available, the module falls back to the
        other known PHP binary when present.
    type: str
    required: false
    default: php

  php_dependencies:
    description:
      - List of required PHP modules that must be available for Nextcloud.
      - Module names are matched case-insensitively against the output of
        C(php -m).
    type: list
    elements: str
    required: true

notes:
  - This module does not support check mode.
  - The module only validates the current PHP module state and never installs
    or removes packages.
  - The result always reports C(changed=false) because no target state is
    modified.

attributes:
  check_mode:
    support: none
"""

EXAMPLES = r"""
- name: Validate required PHP modules for the default PHP runtime
  bodsch.cloud.nextcloud_php_dependencies:
    php_dependencies:
      - ctype
      - curl
      - dom
      - gd
      - iconv
      - libxml
      - mbstring
      - openssl
      - posix
      - session
      - simplexml
      - xml
      - xmlreader
      - xmlwriter
      - zip

- name: Validate required PHP modules for php-legacy
  bodsch.cloud.nextcloud_php_dependencies:
    package_name: php-legacy
    php_dependencies:
      - ctype
      - curl
      - gd
      - mbstring
      - openssl
      - zip
"""

RETURN = r"""
changed:
  description:
    - Indicates whether the module changed the target system.
    - This module is read-only and therefore always returns C(false).
  returned: always
  type: bool
  sample: false

failed:
  description:
    - Indicates whether module execution failed.
    - The module fails when the PHP binary cannot be found, when C(php -m)
      cannot be executed successfully, or when required PHP modules are missing.
  returned: always
  type: bool
  sample: false

msg:
  description:
    - Human-readable validation result.
    - Contains either a success message, a missing dependency summary, or an
      execution error description.
  returned: always
  type: str
  sample: All required PHP modules are installed.
"""

# ---------------------------------------------------------------------------------------


class ValidationResult(TypedDict):
    """Typed result structure returned by :meth:`NextcloudPHPDependencies.run`."""

    changed: bool
    failed: bool
    msg: str


class NextcloudPHPDependencies:
    """Validate PHP module availability for Nextcloud requirements.

    The class encapsulates PHP runtime detection, execution of ``php -m``,
    parsing of the available module list, and case-insensitive comparison
    against the configured dependency list.
    """

    module: AnsibleModule

    def __init__(self, module: AnsibleModule) -> None:
        """Initialize the validator from the active Ansible module instance.

        Args:
            module: Active Ansible module instance providing parameters,
                binary lookup, command execution, and logging helpers.
        """
        self.module = module

        params = cast(Dict[str, Any], module.params)

        self.package_name: str = str(params.get("package_name", "php")).strip() or "php"
        self.php_dependencies: List[str] = self.__normalize_dependencies(
            cast(Sequence[Any], params.get("php_dependencies") or [])
        )

        self.php_legacy_binary: Optional[str] = self.module.get_bin_path(
            "php-legacy", False
        )
        self.php_binary: Optional[str] = self.module.get_bin_path("php", False)

        self._last_error: Optional[str] = None

    def run(self) -> Dict[str, Any]:
        """Execute the validation and return an Ansible-compatible result.

        Returns:
            A result dictionary containing ``changed``, ``failed``, and ``msg``.
        """
        modules, error = self.php_modules()
        if error:
            message = self._last_error or "Unable to determine installed PHP modules."
            return ValidationResult(changed=False, failed=True, msg=message)

        if not self.php_dependencies:
            return ValidationResult(
                changed=False,
                failed=False,
                msg="No PHP dependencies defined.",
            )

        available_modules, missing_modules = self.check_dependencies(modules=modules)

        if missing_modules:
            return ValidationResult(
                changed=False,
                failed=True,
                msg=f"Missing PHP modules: {', '.join(missing_modules)}",
            )

        return ValidationResult(
            changed=False,
            failed=False,
            msg="All required PHP modules are installed.",
        )

    def php_modules(self) -> Tuple[List[str], bool]:
        """Read the currently available PHP modules from the selected runtime.

        The public return shape is intentionally preserved as a tuple of
        ``(modules, error)``.

        Returns:
            Tuple containing the detected module list and an error flag.
            The error flag is ``True`` if the runtime could not be inspected.
        """
        self._last_error = None
        php_binary = self.__resolve_php_binary()

        if not php_binary:
            self._last_error = (
                "Neither 'php' nor 'php-legacy' is available on the target host."
            )
            return [], True

        args = [php_binary, "-m"]
        rc, out, err = self._exec(args, check_rc=False)

        if rc != 0:
            stderr = err.strip() or "Unknown error"
            self._last_error = f"Unable to execute '{php_binary} -m': {stderr}"
            return [], True

        modules = self.__parse_php_modules(out)

        return modules, False

    def check_dependencies(self, modules: List[str]) -> Tuple[List[str], List[str]]:
        """Check whether all configured PHP dependencies are available.

        Args:
            modules: Module names returned by :meth:`php_modules`.

        Returns:
            Tuple of ``(available_modules, missing_modules)`` preserving the
            original dependency order.
        """
        normalized_modules = {module.lower() for module in modules}

        available_modules = [
            dependency
            for dependency in self.php_dependencies
            if dependency.lower() in normalized_modules
        ]
        missing_modules = [
            dependency
            for dependency in self.php_dependencies
            if dependency.lower() not in normalized_modules
        ]

        return available_modules, missing_modules

    def _exec(
        self,
        args: List[str],
        environ_update: Optional[Dict[str, str]] = None,
        check_rc: bool = True,
    ) -> Tuple[int, str, str]:
        """Execute a prepared command via ``AnsibleModule.run_command``.

        Args:
            args: Full argument vector to execute.
            environ_update: Optional environment variables added or overridden
                for the process.
            check_rc: If ``True``, Ansible fails on non-zero exit codes.

        Returns:
            Tuple of ``(rc, out, err)``.
        """
        # self.module.log(
        #     "NextcloudPHPDependencies::_exec("
        #     f"args: {args}, environ_update: {environ_update}, "
        #     f"check_rc: {check_rc})"
        # )

        rc, out, err = self.module.run_command(
            args,
            environ_update=environ_update,
            check_rc=check_rc,
        )

        return rc, out, err

    def __resolve_php_binary(self) -> Optional[str]:
        """Resolve the preferred PHP binary from the configured package name.

        Returns:
            Absolute path of a suitable PHP binary if available, otherwise
            ``None``.
        """
        if self.package_name == "php-legacy":
            return self.php_legacy_binary or self.php_binary

        return self.php_binary or self.php_legacy_binary

    def __normalize_dependencies(self, dependencies: Sequence[Any]) -> List[str]:
        """Normalize the configured PHP dependency list.

        Args:
            dependencies: Raw dependency values from module parameters.

        Returns:
            Cleaned dependency list with stripped string values and empty entries
            removed.
        """
        normalized: List[str] = []

        for dependency in dependencies:
            value = str(dependency).strip()
            if value:
                normalized.append(value)

        return normalized

    def __parse_php_modules(self, output: str) -> List[str]:
        """Parse the output of ``php -m`` into a normalized module list.

        Args:
            output: Raw stdout returned by ``php -m``.

        Returns:
            Lowercase list of PHP module names without section headers or empty
            lines.
        """
        modules: List[str] = []

        for line in output.splitlines():
            value = line.strip()
            if not value or value.startswith("["):
                continue
            modules.append(value.lower())

        return modules


def main() -> None:
    """Create the Ansible module wrapper and execute the validator."""
    spec = dict(
        package_name=dict(
            required=False,
            default="php",
            type="str",
        ),
        php_dependencies=dict(
            required=True,
            type="list",
            elements="str",
        ),
    )

    module = AnsibleModule(
        argument_spec=spec,
        supports_check_mode=False,
    )

    helper = NextcloudPHPDependencies(module)
    result = helper.run()

    module.log(msg=f" = result : '{result}'")
    module.exit_json(**result)


if __name__ == "__main__":
    main()
