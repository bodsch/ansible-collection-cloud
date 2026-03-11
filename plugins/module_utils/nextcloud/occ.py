#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
occ.py

Thin wrapper around Nextcloud's `occ` CLI for usage inside Ansible modules.

This module provides a small helper class (`Occ`) that:
- validates a Nextcloud installation path (presence of the `occ` script and working directory),
- runs common `occ` commands (`status`, `check`, `upgrade`, `maintenance:install`, etc.),
- parses JSON output where supported,
- normalizes certain error messages for better Ansible reporting.

Implementation notes
--------------------
- Commands are executed via `AnsibleModule.run_command()`.
- The class uses `sudo` to switch to the Nextcloud owner (commonly `www-data`).
- For password-based user creation (via `--password-from-env`) the environment variable
  `OC_PASS` is expected to be visible to the `occ` process. Depending on `sudoers`,
  you may need `--preserve-env=OC_PASS` (already configured in `occ_base_args`).

Security note
-------------
Be careful with logging: if you pass secrets via `environ_update` (e.g. `OC_PASS`),
do not log them verbatim in production environments.
"""

from __future__ import absolute_import, print_function

import json
import os
import re
import shutil
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Union,
    overload,
)


class AnsibleModuleLike(Protocol):
    def run_command(
        self,
        args: Sequence[str],
        cwd: Optional[str] = None,
        environ_update: Optional[Mapping[str, str]] = None,
        check_rc: bool = True,
    ) -> Tuple[int, str, str]:
        ...

    def log(self, msg: str = "", **kwargs: Any) -> None:
        ...


_UNHANDLED_EXCEPTION_RE = re.compile(
    r"(?P<message>[\s\S]*?)An unhandled exception has been thrown:\n(?P<exception>[^\n]+)",
    re.MULTILINE,
)
_UPGRADE_REQUIRED_RE = re.compile(
    r"Nextcloud or one of the apps require upgrade.*", re.MULTILINE
)
_NOT_INSTALLED_RE = re.compile(r"Nextcloud is not installed.*", re.MULTILINE)


class Occ:
    """
    Helper to execute Nextcloud's `occ` CLI in a controlled way for Ansible modules.

    The class prepares a common base command (`occ_base_args`) and offers methods
    for typical lifecycle and configuration tasks. All commands are executed in the
    configured `working_dir`, which should be the Nextcloud installation directory
    containing the `occ` script.

    Attributes:
        module: Ansible module object (typically `ansible.module_utils.basic.AnsibleModule`)
            providing `run_command()` and `log()`.
        owner: Unix user that should execute `occ` (commonly `www-data`).
        working_dir: Nextcloud installation directory where the `occ` script lives.
        occ_base_args: Base argument vector used for all `occ` calls.
        _occ: Full path to the `occ` script (working_dir/occ).

    Typical usage:
        occ = Occ(module, owner="www-data", working_dir="/var/www/nextcloud")
        error, msg = occ.self_check()
        if error:
            module.fail_json(**msg)
        rc, installed, version, needs_db_upgrade, err = occ.status()
    """

    module: AnsibleModuleLike

    def __init__(self, module: AnsibleModuleLike, owner: str, working_dir: str) -> None:
        """
        Initialize the wrapper.

        Args:
            module: An Ansible module instance providing `run_command()` and `log()`.
            owner: Target OS user that should run the `occ` command.
            working_dir: Nextcloud installation directory (must exist and contain `occ`).

        Side effects:
            - Builds `self._occ` as `<working_dir>/occ`.
            - Initializes `occ_base_args` using `sudo` and PHP to run `occ`.
        """
        self.module = module

        # self.module.log(f"Occ::__init__({owner}, {working_dir})")

        self.owner = owner
        self.working_dir = working_dir
        self._occ = os.path.join(self.working_dir, "occ")

        _php = "php"
        _php_legacy_binary = self.module.get_bin_path("php-legacy", False)
        # _php_binary = self.module.get_bin_path("php", False)

        if _php_legacy_binary:
            _php = "php-legacy"

        # Base command used for all `occ` invocations.
        #
        # `--preserve-env=OC_PASS` is needed when `occ` relies on `--password-from-env`.
        # Whether this works depends on your `sudoers` configuration.
        self.occ_base_args: List[str] = [
            "sudo",
            "--preserve-env=OC_PASS",
            "--user",
            self.owner,
            _php,
            "occ",
        ]

    @staticmethod
    def _extract_unhandled_exception(text: str) -> str:
        """
        Extract the exception line from Nextcloud's typical "unhandled exception" output.

        If the pattern does not match, the original text is returned unchanged.
        """
        match = re.search(_UNHANDLED_EXCEPTION_RE, text)

        message = None
        exception = None
        if match:
            message = match.group("message")
            exception = match.group("exception")

        if message:
            return message
        if exception:
            return exception

        return text

    @staticmethod
    def _redact_env(
        environ_update: Optional[Mapping[str, str]],
    ) -> Optional[Dict[str, str]]:
        """
        Redact sensitive environment values before logging.

        Keys containing PASS, PASSWORD, SECRET, TOKEN are replaced with '<redacted>'.
        """
        if environ_update is None:
            return None

        redacted: Dict[str, str] = {}
        for k, v in environ_update.items():
            upper = k.upper()
            if any(s in upper for s in ("PASS", "PASSWORD", "SECRET", "TOKEN")):
                redacted[k] = "<redacted>"
            else:
                redacted[k] = v
        return redacted

    def _build_args(self, *parts: str) -> List[str]:
        """
        Build an `occ` command by extending `occ_base_args` with additional parts.
        """
        return [*self.occ_base_args, *parts]

    def self_check(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate that the `occ` script and working directory are present.

        Returns:
            A tuple of:
            - error (bool): True if validation failed.
            - msg (dict): An Ansible-style result dictionary containing at least:
                - failed (bool)
                - changed (bool)
                - msg (str)

        Side effects:
            Changes the process working directory to `self.working_dir` if it exists.

        Notes:
            This method does not raise exceptions for missing paths; it returns
            an error flag and an Ansible-compatible message payload.
        """
        # self.module.log("Occ::self_check()")

        error = False
        msg: Dict[str, Any] = {}

        if not os.path.exists(self._occ):
            error = True
            msg = dict(failed=True, changed=False, msg="missing occ")

        if os.path.exists(self.working_dir):
            os.chdir(self.working_dir)
        else:
            error = True
            msg = dict(
                failed=True,
                changed=False,
                msg=f"missing working directory '{self.working_dir}'",
            )

        return error, msg

    def status(self) -> Tuple[int, bool, Optional[str], bool, str]:
        """
        Run `occ status` and return installation and version details.

        Command executed:
            sudo -u <owner> php occ status --no-ansi --output json

        Returns:
            Tuple of:
            - rc (int): Command return code.
            - installed (bool): Whether Nextcloud reports itself as installed.
            - version_string (Optional[str]): Human-readable version string (e.g. "29.0.1").
            - db_upgrade (bool): Whether a DB upgrade is required.
            - err (str): Parsed error message or raw output in error cases.

        Notes:
            - Parses JSON output when rc == 0.
            - If rc != 0, tries to extract the exception line from the typical
              "An unhandled exception has been thrown" output.
        """
        # self.module.log("Occ::status()")

        installed = False
        version_string: Optional[str] = None
        db_upgrade = False
        err_msg = ""

        args = self._build_args("status", "--no-ansi", "--output", "json")

        rc, out, err = self._exec(args, check_rc=False)

        # self.module.log(msg=f" rc : '{rc}'")
        # self.module.log(msg=f" out: '{out.strip()}'")
        # self.module.log(msg=f" err: '{err.strip()}'")

        if rc == 0:
            try:
                parsed: Dict[str, Any] = json.loads(out)
                installed = bool(parsed.get("installed", False))
                version_string = parsed.get("versionstring", None)
                db_upgrade = bool(parsed.get("needsDbUpgrade", False))
            except json.JSONDecodeError as e:
                # Keep behavior non-raising; report parse issues as an error message.
                err_msg = f"Failed to parse occ JSON output: {e}"
                return (1, False, None, False, err_msg)
        else:
            # Nextcloud frequently prints fatal details to stdout; normalize from stdout first.
            err_msg = self._extract_unhandled_exception(out.strip() or err.strip())

        return (rc, installed, version_string, db_upgrade, err_msg or err.strip())

    def upgrade(self) -> Tuple[int, str, str]:
        """
        Run `occ upgrade`.

        Command executed:
            sudo -u <owner> php occ upgrade --no-ansi

        Returns:
            Tuple of:
            - rc (int): Command return code.
            - out (str): Stdout
            - err (str): Stderr or normalized success/error message

        Notes:
            In case of exceptions, tries to extract a single-line exception message
            from typical Nextcloud output.
        """
        # self.module.log("Occ::upgrade()")

        args = self._build_args("upgrade", "--no-ansi")

        # self.module.log(msg=f" args: '{args}'")

        rc, out, err = self._exec(args, check_rc=False)

        # self.module.log(msg=f" rc : '{rc}'")
        # self.module.log(msg=f" out: '{out.strip()}'")
        # self.module.log(msg=f" err: '{err.strip()}'")

        if rc == 0:
            # self.module.log(msg="okay?")
            err = "The upgrade was successful."
        else:
            err = self._extract_unhandled_exception(out.strip() or err.strip())

        # self.module.log(msg=f"= rc: {rc}, out: {out.strip()}, err: {err.strip()}")
        return (rc, out, err)

    @overload
    def check(
        self, check_installed: Literal[False] = False
    ) -> Tuple[int, str, str]:
        ...

    @overload
    def check(self, check_installed: Literal[True]) -> Tuple[int, bool, str, str]:
        ...

    def check(
        self, check_installed: bool = False
    ) -> Union[Tuple[int, str, str], Tuple[int, bool, str, str]]:
        """
        Run `occ check` and optionally determine if Nextcloud is installed.

        Command executed:
            sudo -u <owner> php occ check --no-ansi --output json

        Args:
            check_installed: If True, attempts to interpret output to decide whether
                Nextcloud is installed, and may trigger an upgrade when needed.

        Returns:
            If check_installed is False:
                (rc, out, err)
            If check_installed is True:
                (rc, installed, out, err)

        Notes:
            - `occ check` may return rc==0 but still indicate that an upgrade is needed.
            - In check_installed=True mode, this method:
                * detects upgrade-required messages and triggers `upgrade()`
                * detects "Nextcloud is not installed" messages

        Caveat:
            The correctness of `installed` detection depends on Nextcloud's output
            format and may need adjustments across versions.
        """
        # self.module.log(f"Occ::check(check_installed: {check_installed})")

        args = self._build_args("check", "--no-ansi", "--output", "json")
        rc, out, err = self._exec(args, check_rc=False)

        if not check_installed:
            # self.module.log(f"  - rc: {rc}")
            # self.module.log(f"  - out: {out.strip()}")
            # self.module.log(f"  - err: {err.strip()}")

            if rc == 0:
                need_upgrade = re.search(_UPGRADE_REQUIRED_RE, err) or re.search(
                    _UPGRADE_REQUIRED_RE, out
                )
                if need_upgrade:
                    out = (
                        "Nextcloud or one of the apps require upgrade.\n"
                        "You may use your browser or the occ upgrade command to do the upgrade."
                    )
                    rc = 1

            return rc, out, err

        installed = False

        if rc == 0:
            need_upgrade = re.search(_UPGRADE_REQUIRED_RE, err) or re.search(
                _UPGRADE_REQUIRED_RE, out
            )
            if need_upgrade:
                installed = False
                self.upgrade()

            is_installed = re.search(_NOT_INSTALLED_RE, err) or re.search(
                _NOT_INSTALLED_RE, out
            )
            installed = not bool(is_installed)
        else:
            err = self._extract_unhandled_exception(out.strip() or err.strip())

        # self.module.log(f"  - rc: {rc}")
        # self.module.log(f"  - out: {out.strip()}")
        # self.module.log(f"  - err: {err.strip()}")
        # self.module.log(f"  - installed: {installed}")

        # self.module.log(
        #     msg=f"= rc: {rc}, installed: {installed}, out: {out.strip()}, err: {err.strip()}"
        # )

        return (rc, installed, out, err)

    def maintenance_install(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run `occ maintenance:install` to initialize a fresh Nextcloud instance.

        Command executed (example):
            sudo -u <owner> php occ maintenance:install
                --database mysql
                --database-host <host>
                --database-port <port>
                --database-name <schema>
                --database-user <user>
                --database-pass <pass>
                --admin-user <admin>
                --admin-pass <admin-pass>
                --no-ansi

        Args:
            config: Installation parameters. Expected structure:
                {
                  "data_dir": "<optional path>",
                  "database": {
                    "type": "mysql",
                    "hostname": "...",
                    "port": "...",
                    "schema": "...",
                    "username": "...",
                    "password": "..."
                  },
                  "admin": {
                    "username": "...",
                    "password": "..."
                  }
                }

        Returns:
            An Ansible-style result dict containing:
                - failed (bool)
                - changed (bool)
                - msg (str)

        Side effects:
            - On success, creates a backup of config/config.php to config/config.bck
            - Writes config/config.json via `config_list()`

        Notes:
            On failure, tries to match common error patterns to provide a concise message.
        """
        # self.module.log(f"Occ::maintenance_install({config})")

        _failed = True
        _changed = False

        database: Dict[str, Any] = config.get("database", {}) or {}
        admin: Dict[str, Any] = config.get("admin", {}) or {}

        data_dir = config.get("data_dir", None)
        dba_type = database.get("type", None)
        dba_hostname = database.get("hostname", None)
        dba_port = database.get("port", None)
        dba_schema = database.get("schema", None)
        dba_username = database.get("username", None)
        dba_password = database.get("password", None)
        admin_username = admin.get("username", None)
        admin_password = admin.get("password", None)

        # Minimal validation to avoid appending None into argv.
        missing: List[str] = []
        if not dba_type:
            missing.append("database.type")
        if not admin_username:
            missing.append("admin.username")
        if not admin_password:
            missing.append("admin.password")

        if dba_type == "mysql":
            for key_name, key_value in (
                ("database.hostname", dba_hostname),
                ("database.port", dba_port),
                ("database.schema", dba_schema),
                ("database.username", dba_username),
                ("database.password", dba_password),
            ):
                if not key_value:
                    missing.append(key_name)

        if missing:
            return dict(
                failed=True,
                changed=False,
                msg=f"Missing required parameters for maintenance:install: {', '.join(missing)}",
            )

        args: List[str] = []
        args += self.occ_base_args
        args.append("maintenance:install")

        if data_dir:
            args.append("--data-dir")
            args.append(str(data_dir))

        args.append("--database")
        args.append(str(dba_type))

        if dba_type == "mysql":
            args += ["--database-host", str(dba_hostname)]
            args += ["--database-port", str(dba_port)]
            args += ["--database-name", str(dba_schema)]
            args += ["--database-user", str(dba_username)]
            args += ["--database-pass", str(dba_password)]

        args += ["--admin-user", str(admin_username)]
        args += ["--admin-pass", str(admin_password)]
        args.append("--no-ansi")

        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            _msg = "database was successfully created."
            _failed = False
            _changed = True

            _config_file = os.path.join(self.working_dir, "config", "config.php")
            _config_backup = os.path.join(self.working_dir, "config", "config.bck")

            shutil.copyfile(_config_file, _config_backup)

            self.config_list()
        else:
            patterns = [
                '.*Command "maintenance:install" is not defined.*',
                "Database .* is not supported.",
                "Following symlinks is not allowed",
                "Username is invalid because files already exist for this user",
                "Login is invalid because files already exist for this user",
            ]
            error: Optional[str] = None

            _output: List[str] = []
            _output += out.splitlines()
            _output += err.splitlines()

            # self.module.log(f" - {_output}")

            for pattern in patterns:
                filter_list = list(filter(lambda x: re.search(pattern, x), _output))
                if len(filter_list) > 0 and isinstance(filter_list, list):
                    error = (filter_list[0]).strip()
                    # self.module.log(msg=f"  - {error}")
                    break

            _, installed, version, _, status_err = self.status()

            if rc == 0 and not error and installed:
                _failed = False
                _changed = False
                _msg = f"Nextcloud {version} already installed."
            else:
                _failed = True
                _changed = False
                _msg = (
                    error
                    or status_err
                    or out.strip()
                    or err.strip()
                    or "Unknown error."
                )

        return dict(failed=_failed, changed=_changed, msg=_msg)

    def background_job(self, crontype: str) -> Dict[str, Any]:
        """
        Configure the Nextcloud background job mode.

        Command executed:
            sudo -u <owner> php occ background:<crontype> --no-ansi

        Args:
            crontype: Background job type (e.g. "ajax", "webcron", "cron").

        Returns:
            An Ansible-style dict:
                - failed (bool): True if the command return code is non-zero
                - msg (str): Stdout content (trimmed)
        """
        # self.module.log(f"Occ::background_job({crontype})")

        args = self._build_args(f"background:{crontype}", "--no-ansi")
        rc, out, err = self._exec(args, check_rc=False)

        return dict(failed=not (rc == 0), msg=out.strip())

    def config_list(self, type: str = "system") -> Dict[str, Any]:
        """
        Export Nextcloud configuration to a JSON file.

        Command executed (currently hardcoded to `system`):
            sudo -u <owner> php occ config:list system --no-ansi

        Args:
            type: Intended config scope (currently unused; kept for API compatibility).

        Returns:
            An Ansible-style dict:
                - failed (bool)
                - changed (bool)

        Side effects:
            On success, writes `<working_dir>/config/config.json` with the command output.

        Notes:
            The function currently always calls `config:list system` regardless of `type`.
        """
        # self.module.log(f"Occ::config_list({type})")

        args: List[str] = []
        args += self.occ_base_args

        args.append("config:list")
        args.append("system")
        args.append("--no-ansi")

        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            file_name = os.path.join(self.working_dir, "config", "config.json")
            with open(file_name, "w") as f:
                f.write(out)

        return dict(
            failed=False,
            changed=False,
        )

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
        # self.module.log(
        #     msg=f"Occ::_exec(args: {args}, environ_update: {self._redact_env(environ_update)}, check_rc: {check_rc})"
        # )

        rc, out, err = self.module.run_command(
            args, cwd=self.working_dir, environ_update=environ_update, check_rc=check_rc
        )

        return rc, out, err
