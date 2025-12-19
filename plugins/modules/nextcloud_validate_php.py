#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2025, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
Ansible module: nextcloud_validate_php

This module validates whether a given PHP version is compatible with a specific
Nextcloud release by reading Nextcloud's `lib/versioncheck.php` from the official
Nextcloud GitHub repository and deriving version constraints from it.

How it works
------------
- Builds a GitHub URL for `lib/versioncheck.php` using the provided Nextcloud version.
- Downloads the file (via GitHub raw content URL conversion).
- Parses `if (PHP_VERSION_ID <op> <number>) { ... }` checks and derives:
  - minimum supported PHP_VERSION_ID (inclusive),
  - maximum supported PHP_VERSION_ID (exclusive),
  - explicitly excluded PHP_VERSION_ID values.
- Converts the provided `php_version` string to a PHP_VERSION_ID integer and checks it.

Notes / Limitations
-------------------
- This uses a heuristic parser for constraints. It covers Nextcloud's common pattern,
  but it is not a full PHP parser.
- The module performs an outbound HTTP request to GitHub to read version constraints.
- The parameters `from_git` and `from_archive` exist in the argument spec but are
  currently not used in the implementation.

Return values
-------------
The module returns a compatibility decision and the derived constraints in a structured way.
"""

from __future__ import absolute_import, print_function

import re
from dataclasses import dataclass
from typing import Optional, Pattern, Set, TypedDict, cast
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from ansible.module_utils.basic import AnsibleModule

# ---------------------------------------------------------------------------------------

DOCUMENTATION = r"""
---
module: nextcloud_validate_php
author: "Bodo Schulz (@bodsch) <bodo@boone-schulz.de>"
version_added: "1.2.0"

short_description: Validate PHP version compatibility for a specific Nextcloud release.
description:
  - Downloads Nextcloud's C(lib/versioncheck.php) for a given Nextcloud version tag and
    derives PHP compatibility constraints from the checks in that file.
  - Converts a provided PHP version string to a numeric C(PHP_VERSION_ID) and validates
    it against the derived constraints.
  - Intended to be used in automation pipelines to fail early if the targeted PHP
    version is not supported by the requested Nextcloud release.

options:
  nextcloud_version:
    description:
      - Nextcloud version tag (without leading 'v'), e.g. C(32.0.3).
      - Used to build the GitHub URL C(https://github.com/nextcloud/server/blob/v<version>/lib/versioncheck.php).
    type: str
    required: true
  php_version:
    description:
      - PHP version string to validate, e.g. C(8.2.12) or C(PHP 8.2.12 (cli) ...).
      - The first occurrence of a semantic version-like pattern is used.
    type: str
    required: true
  from_git:
    description:
      - Reserved for future use. Currently unused by the implementation.
    type: bool
    required: true
  from_archive:
    description:
      - Reserved for future use. Currently unused by the implementation.
    type: bool
    required: false

requirements:
  - python >= 3.8

notes:
  - The module performs an HTTP request to GitHub to fetch C(versioncheck.php).
  - Parsing is heuristic and based on common Nextcloud patterns using C(PHP_VERSION_ID).
"""

EXAMPLES = r"""
- name: Validate PHP version against Nextcloud 32.0.3 requirements
  nextcloud_validate_php:
    nextcloud_version: "32.0.3"
    php_version: "8.2.12"
    from_git: true
  register: php_check

- name: Fail if PHP is incompatible
  ansible.builtin.fail:
    msg: "Incompatible PHP version: {{ php_check.reason }}"
  when: not php_check.compatible

- name: Show derived constraints
  ansible.builtin.debug:
    msg:
      - "PHP_VERSION_ID: {{ php_check.php_version_id }}"
      - "Min: {{ php_check.php_min_inclusive }}"
      - "Max: {{ php_check.php_max_exclusive }}"
      - "Excluded: {{ php_check.excluded }}"
"""

RETURN = r"""
compatible:
  description: Whether the provided PHP version is compatible with the selected Nextcloud release.
  returned: always
  type: bool
php_version_id:
  description: The numeric PHP_VERSION_ID derived from the provided php_version string.
  returned: always
  type: int
php_min_inclusive:
  description: Minimum supported PHP version (inclusive) derived from versioncheck.php, formatted as x.y.z.
  returned: always
  type: str
  sample: "8.1.0"
php_max_exclusive:
  description: Maximum supported PHP version (exclusive) derived from versioncheck.php, formatted as x.y.z.
  returned: always
  type: str
  sample: "8.4.0"
excluded:
  description: Explicitly excluded PHP versions derived from versioncheck.php, formatted as x.y.z.
  returned: always
  type: list
  elements: str
reason:
  description: Human-readable decision explanation.
  returned: always
  type: str
"""

# ---------------------------------------------------------------------------------------

# Compiled regex patterns (performance + single source of truth)
_CONSTRAINT_IF_RE: Pattern[str] = re.compile(
    r"""if\s*\(\s*PHP_VERSION_ID\s*(<=|>=|<|>|==|===)\s*([0-9]{5,6})\s*\)\s*\{""",
    re.MULTILINE,
)
_PHP_VERSION_RE: Pattern[str] = re.compile(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?")


class PhpCompatibilityResult(TypedDict):
    compatible: bool
    php_version_id: int
    php_min_inclusive: Optional[str]
    php_max_exclusive: Optional[str]
    excluded: list[str]
    reason: str


@dataclass(frozen=True)
class PhpVersionConstraints:
    """
    Container for PHP compatibility constraints derived from Nextcloud's versioncheck.php.

    Fields:
      - min_inclusive_id: Minimum PHP_VERSION_ID that is considered supported (inclusive).
      - max_exclusive_id: Maximum PHP_VERSION_ID that is considered supported (exclusive).
      - excluded_ids: A set of PHP_VERSION_ID values that are explicitly not supported.

    Nextcloud expresses constraints using PHP_VERSION_ID, where:
      PHP_VERSION_ID = major*10000 + minor*100 + patch
    """

    min_inclusive_id: Optional[int] = None  # PHP_VERSION_ID >= this
    max_exclusive_id: Optional[int] = None  # PHP_VERSION_ID < this
    excluded_ids: frozenset[int] = (
        frozenset()
    )  # PHP_VERSION_ID must NOT be any of these

    @staticmethod
    def id_to_version(version_id: int) -> str:
        """
        Convert a PHP_VERSION_ID integer into a dotted version string (major.minor.patch).

        Example:
          80212 -> "8.2.12"
        """
        major = version_id // 10000
        minor = (version_id % 10000) // 100
        patch = version_id % 100
        return f"{major}.{minor}.{patch}"


class NextcloudValidatePHPVersion:
    """
    Validator that checks a PHP version against the PHP requirements of a given Nextcloud version.

    The validator:
      1) Builds the URL to Nextcloud's `lib/versioncheck.php` for the given Nextcloud version tag.
      2) Downloads the PHP source from GitHub.
      3) Parses PHP_VERSION_ID constraint checks.
      4) Compares the provided PHP version (converted to PHP_VERSION_ID) to those constraints.

    The class is designed to be instantiated with an AnsibleModule instance to allow logging and
    access to module parameters.
    """

    module: AnsibleModule
    versioncheck_file: str
    nextcloud_version: str
    php_version: str

    def __init__(self, module: AnsibleModule) -> None:
        """
        Initialize the handler from Ansible module parameters.

        Expected module parameters:
          - nextcloud_version (str): Nextcloud release version (without leading 'v')
          - php_version (str): PHP version string that can be parsed into major/minor/patch
        """
        self.module = module

        # Required by argument_spec -> safe to cast for typing purposes
        self.nextcloud_version = cast(str, module.params.get("nextcloud_version"))
        self.php_version = cast(str, module.params.get("php_version"))
        self.versioncheck_file = f"https://github.com/nextcloud/server/blob/v{self.nextcloud_version}/lib/versioncheck.php"

        # self.module.log("NextcloudValidatePHPVersion::__init__()")

    def run(self) -> PhpCompatibilityResult:
        """
        Execute the module's main logic and return the result dict for Ansible.

        Returns:
          A dictionary suitable for AnsibleModule.exit_json(...).
        """
        # self.module.log("NextcloudValidatePHPVersion::run()")

        return self.check_php_compatibility(
            versioncheck_url=self.versioncheck_file,
        )

    def check_php_compatibility(
        self,
        versioncheck_url: str,
        timeout_seconds: int = 10,
    ) -> PhpCompatibilityResult:
        """
        Check whether the provided PHP version is compatible with Nextcloud's version requirements.

        The PHP version is taken from the module parameter `php_version` and converted to an integer
        PHP_VERSION_ID. The constraints are derived from the referenced Nextcloud versioncheck.php.

        Args:
          versioncheck_url: GitHub URL (blob or raw) to Nextcloud's lib/versioncheck.php.
          timeout_seconds: HTTP timeout when fetching the versioncheck.php source.

        Returns:
          A dict with:
            - compatible (bool)
            - php_version_id (int)
            - php_min_inclusive (str|None)
            - php_max_exclusive (str|None)
            - excluded (list[str])
            - reason (str)
        """
        # self.module.log(
        #     f"NextcloudValidatePHPVersion::check_php_compatibility({versioncheck_url})"
        # )

        php_source = self._fetch_text(versioncheck_url, timeout_seconds=timeout_seconds)
        constraints = self._parse_constraints(php_source)
        php_vid = self.php_version_to_vid(self.php_version)

        excluded_versions = [
            PhpVersionConstraints.id_to_version(v)
            for v in sorted(constraints.excluded_ids)
        ]

        min_str = (
            PhpVersionConstraints.id_to_version(constraints.min_inclusive_id)
            if constraints.min_inclusive_id is not None
            else None
        )
        max_str = (
            PhpVersionConstraints.id_to_version(constraints.max_exclusive_id)
            if constraints.max_exclusive_id is not None
            else None
        )

        if (
            constraints.min_inclusive_id is not None
            and php_vid < constraints.min_inclusive_id
        ):
            return {
                "compatible": False,
                "php_version_id": php_vid,
                "php_min_inclusive": min_str,
                "php_max_exclusive": max_str,
                "excluded": excluded_versions,
                "reason": (
                    f"PHP {PhpVersionConstraints.id_to_version(php_vid)} is below minimum "
                    f"{PhpVersionConstraints.id_to_version(constraints.min_inclusive_id)}."
                ),
            }

        if (
            constraints.max_exclusive_id is not None
            and php_vid >= constraints.max_exclusive_id
        ):
            return {
                "compatible": False,
                "php_version_id": php_vid,
                "php_min_inclusive": min_str,
                "php_max_exclusive": max_str,
                "excluded": excluded_versions,
                "reason": (
                    f"PHP {PhpVersionConstraints.id_to_version(php_vid)} is not supported (>= "
                    f"{PhpVersionConstraints.id_to_version(constraints.max_exclusive_id)})."
                ),
            }

        if php_vid in constraints.excluded_ids:
            return {
                "compatible": False,
                "php_version_id": php_vid,
                "php_min_inclusive": min_str,
                "php_max_exclusive": max_str,
                "excluded": excluded_versions,
                "reason": (
                    f"PHP {PhpVersionConstraints.id_to_version(php_vid)} is explicitly excluded."
                ),
            }

        return {
            "compatible": True,
            "php_version_id": php_vid,
            "php_min_inclusive": min_str,
            "php_max_exclusive": max_str,
            "excluded": excluded_versions,
            "reason": "OK",
        }

    def _github_blob_to_raw(self, url: str) -> str:
        """
        Convert a GitHub `blob` URL into a `raw.githubusercontent.com` URL.

        Supported:
          - https://github.com/<org>/<repo>/blob/<ref>/<path>
          - raw GitHub URLs are returned unchanged

        Args:
          url: A GitHub URL (blob or raw).

        Returns:
          The raw content URL if conversion is possible, otherwise the original URL.
        """
        # self.module.log(f"NextcloudValidatePHPVersion::_github_blob_to_raw({url})")

        p = urlparse(url)
        if p.netloc.lower() == "raw.githubusercontent.com":
            return url

        if p.netloc.lower() != "github.com":
            return url

        parts = p.path.strip("/").split("/")
        # expected: org/repo/blob/ref/path...
        if len(parts) >= 5 and parts[2] == "blob":
            org, repo, _, ref = parts[:4]
            path = "/".join(parts[4:])
            # handle URL-encoded slashes (your link uses lib%2Fversioncheck.php)
            path = unquote(path)
            return f"https://raw.githubusercontent.com/{org}/{repo}/{ref}/{path}"

        return url

    def _fetch_text(self, url: str, timeout_seconds: int = 10) -> str:
        """
        Download text content from a URL, typically a GitHub versioncheck.php file.

        Args:
          url: GitHub `blob` or raw URL.
          timeout_seconds: HTTP timeout.

        Returns:
          The decoded text content (UTF-8, replacement on decode errors).

        Raises:
          URLError / HTTPError: If the request fails.
        """
        # self.module.log(
        #     f"NextcloudValidatePHPVersion::_fetch_text({url}, {timeout_seconds})"
        # )

        raw_url = self._github_blob_to_raw(url)
        req = Request(
            raw_url,
            headers={
                "User-Agent": "php-versioncheck-python/1.0",
                "Accept": "text/plain, text/*;q=0.9, */*;q=0.1",
            },
        )
        with urlopen(req, timeout=timeout_seconds) as resp:
            data = resp.read()

        return data.decode("utf-8", errors="replace")

    def _parse_constraints(self, php_source: str) -> PhpVersionConstraints:
        """
        Parse PHP_VERSION_ID checks from the given PHP source and derive version constraints.

        The parser searches for patterns like:
          if (PHP_VERSION_ID < 80100) {
          if (PHP_VERSION_ID >= 80400) {
          if (PHP_VERSION_ID == 80201) {

        Mapping:
          - `PHP_VERSION_ID < X`  => min supported is X (inclusive)
          - `PHP_VERSION_ID <= X` => min supported is X+1
          - `PHP_VERSION_ID >= X` => max supported is X (exclusive)
          - `PHP_VERSION_ID > X`  => max supported is X+1
          - `PHP_VERSION_ID == X` => exclude X

        Args:
          php_source: Raw text contents of Nextcloud's lib/versioncheck.php.

        Returns:
          PhpVersionConstraints derived from the file.
        """
        # Keep the docstring, but avoid logging the full PHP source for performance/security.
        # self.module.log("NextcloudValidatePHPVersion::_parse_constraints()")

        min_incl: Optional[int] = None
        max_excl: Optional[int] = None
        excluded: Set[int] = set()

        for op, num_str in _CONSTRAINT_IF_RE.findall(php_source):
            vid = int(num_str)

            # if (PHP_VERSION_ID < X) => requires >= X
            if op == "<":
                min_incl = vid if min_incl is None else max(min_incl, vid)

            # if (PHP_VERSION_ID <= X) => requires >= (X+1)
            elif op == "<=":
                min_needed = vid + 1
                min_incl = min_needed if min_incl is None else max(min_incl, min_needed)

            # if (PHP_VERSION_ID >= X) => requires < X
            elif op == ">=":
                max_excl = vid if max_excl is None else min(max_excl, vid)

            # if (PHP_VERSION_ID > X) => requires < (X+1)
            elif op == ">":
                max_needed = vid + 1
                max_excl = max_needed if max_excl is None else min(max_excl, max_needed)

            # if (PHP_VERSION_ID == X) => excludes X
            elif op in ("==", "==="):
                excluded.add(vid)

        return PhpVersionConstraints(
            min_inclusive_id=min_incl,
            max_exclusive_id=max_excl,
            excluded_ids=frozenset(excluded),
        )

    def php_version_to_vid(self, version: str) -> int:
        """
        Convert a PHP version string to PHP_VERSION_ID.

        Accepts:
          - "8.2.12"
          - "8.2"
          - "8"
          - "PHP 8.2.12 (cli) (built: ...)"

        The first occurrence of a "major[.minor][.patch]" pattern is used.

        Args:
          version: A string containing a PHP version.

        Returns:
          PHP_VERSION_ID integer: major*10000 + minor*100 + patch

        Raises:
          ValueError: If no version number can be parsed from the string.
        """
        # self.module.log(f"NextcloudValidatePHPVersion::php_version_to_vid({version})")

        m = _PHP_VERSION_RE.search(version)
        if not m:
            raise ValueError(f"Cannot parse PHP version from: {version!r}")

        major = int(m.group(1))
        minor = int(m.group(2) or 0)
        patch = int(m.group(3) or 0)

        return major * 10000 + minor * 100 + patch


def main():
    """
    Ansible module entry point.

    Defines module arguments, instantiates the handler and returns the validation result via
    AnsibleModule.exit_json().
    """
    specs = dict(
        nextcloud_version=dict(required=True, type=str),
        php_version=dict(required=True, type=str),
        from_git=dict(required=True, type=bool),
        from_archive=dict(required=False, type=bool),
    )

    module = AnsibleModule(
        argument_spec=specs,
        supports_check_mode=False,
    )

    handler = NextcloudValidatePHPVersion(module)
    result = handler.run()

    module.exit_json(**result)


if __name__ == "__main__":
    main()
