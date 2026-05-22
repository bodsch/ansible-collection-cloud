#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

"""
apps.py

Nextcloud app management helpers for Ansible modules using the `occ` CLI.

This module provides the :class:`NextcloudApps` helper class, which extends the
base :class:`Occ` wrapper to manage Nextcloud apps via `occ` subcommands, such as:

- install / remove apps
- enable / disable apps (optionally restricted to groups)
- list enabled/disabled apps (JSON output)
- check available app updates and run app updates
- set app config values via `occ config:app:set`

All commands are executed via the Ansible module's ``run_command()`` as prepared
by the parent :class:`Occ` class (e.g., using ``sudo -u www-data php occ``).

Return conventions
------------------
Some methods return Ansible-style dictionaries:

    {"failed": bool, "changed": bool, "msg": str|object}

Other methods return tuples for internal/control-flow usage.

Security note
-------------
Avoid logging sensitive values (e.g. passwords) if they are passed via environment
variables or arguments. While this module does not directly handle passwords, it
invokes `occ` and may operate in an environment where secrets exist.
"""

from __future__ import absolute_import, print_function

import json
import re
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    TypedDict,
    overload,
)

from ansible_collections.bodsch.cloud.plugins.module_utils.nextcloud.occ import Occ


class AnsibleModuleLike(Protocol):
    """ """
    @overload
    def run_command(
        self,
        args: Sequence[str],
        cwd: Optional[str] = None,
        environ_update: Optional[Mapping[str, str]] = None,
        check_rc: bool = True,
    ) -> Tuple[int, str, str]:
        pass

    @overload
    def log(self, msg: str = "", **kwargs: Any) -> None:
        pass


class AnsibleResult(TypedDict, total=False):
    """ """

    failed: bool
    changed: bool
    msg: Any


_UPDATE_AVAILABLE_RE = re.compile(
    r"Update for (?P<app>.*) to version (?P<version>.*) is available.*",
    flags=re.MULTILINE,
)


class NextcloudApps(Occ):
    """
    High-level Nextcloud app management wrapper based on the `occ` CLI.

    This class inherits from :class:`Occ` and uses its prepared command base
    (``self.occ_base_args``) plus the internal ``_exec()`` helper to execute
    `occ` subcommands.

    Parameters:
        module: Ansible module instance (provides `run_command()` and `log()`).
        owner: OS user to run `occ` as (commonly "www-data").
        working_dir: Nextcloud installation directory (contains the `occ` script).

    Notes:
        - Methods typically call `occ` with ``--no-ansi`` for stable parsing.
        - Some methods return Ansible-style dicts; others return tuples.
    """

    module: AnsibleModuleLike

    def __init__(self, module: AnsibleModuleLike, owner: str, working_dir: str) -> None:
        """
        Initialize the NextcloudApps helper.

        Args:
            module: Ansible module instance providing `run_command()` and `log()`.
            owner: The OS user that should execute `occ`.
            working_dir: The Nextcloud installation directory.

        Side effects:
            Calls the parent :class:`Occ` initializer and stores references locally.
        """
        super().__init__(module, owner, working_dir)

        self.module = module

        # self.module.log(f"NextcloudApps::__init__({owner}, {working_dir})")

        self.owner = owner
        self.working_dir = working_dir

    def _build_args(self, *parts: str) -> List[str]:
        args = list(self.occ_base_args)
        args.extend(parts)
        return args

    @staticmethod
    def _best_error(out: str, err: str) -> str:
        msg = out.strip() or err.strip()
        return msg

    def install_app(self, app_name: str) -> Dict[str, Any]:
        """
        Install a Nextcloud app via `occ app:install`.

        Command executed:
            occ app:install --no-ansi --keep-disabled <app_name>

        Args:
            app_name: The Nextcloud app identifier (e.g. "calendar").

        Returns:
            An Ansible-style result dictionary with:
                - failed: True on non-zero return code.
                - changed: True if installation succeeded.
                - msg: Human-readable outcome message or stdout on failure.

        Notes:
            The app is installed but kept disabled (`--keep-disabled`) so that
            enabling can be controlled separately (e.g., group restrictions).
        """
        # self.module.log(f"NextcloudApps::install_app({app_name})")

        args = self._build_args("app:install", "--no-ansi", "--keep-disabled", app_name)
        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            return dict(
                failed=False, changed=True, msg="App was successfully installed."
            )

        return dict(failed=True, changed=False, msg=self._best_error(out, err))

    def remove_app(self, app_name: str) -> Dict[str, Any]:
        """
        Remove a Nextcloud app via `occ app:remove`.

        Command executed:
            occ app:remove --no-ansi <app_name>

        Args:
            app_name: The Nextcloud app identifier.

        Returns:
            An Ansible-style result dictionary with:
                - failed: True on non-zero return code.
                - changed: True if removal succeeded.
                - msg: Human-readable outcome message or stdout on failure.
        """
        # self.module.log(f"NextcloudApps::remove_app({app_name})")

        args = self._build_args("app:remove", "--no-ansi", app_name)
        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            return dict(failed=False, changed=True, msg="App was successfully removed.")

        return dict(failed=True, changed=False, msg=self._best_error(out, err))

    def path_app(self, app_name: str) -> Tuple[bool, bool, bool]:
        """
        Check whether an app path can be resolved via `occ app:getpath`.

        Command executed:
            occ app:getpath --no-ansi <app_name>

        Args:
            app_name: The Nextcloud app identifier.

        Returns:
            Tuple of:
                - failed (bool): True if the command failed (rc != 0).
                - changed (bool): True if the command succeeded (rc == 0).
                  (This mirrors the current implementation; semantically it is a
                  "success" indicator rather than an Ansible state change.)
                - installed (bool): True if the app path was returned successfully.

        Notes:
            This method currently does not return the resolved path, only whether
            it appears to exist (based on command return code).
        """
        # self.module.log(f"NextcloudApps::path_app({app_name})")

        args = self._build_args("app:getpath", "--no-ansi", app_name)
        rc, out, err = self._exec(args, check_rc=False)

        installed = rc == 0
        failed = not installed
        changed = installed

        return (failed, changed, installed)

    def enable_app(
        self, app_name: str, groups: Optional[Sequence[str]] = None
    ) -> Dict[str, Any]:
        """
        Enable a Nextcloud app via `occ app:enable` and optionally restrict to groups.

        Command executed:
            occ app:enable --no-ansi <app_name> [--groups <group> ...]

        Args:
            app_name: The Nextcloud app identifier.
            groups: Optional sequence of Nextcloud group names. If provided, the
                app is enabled for those groups only.

        Returns:
            An Ansible-style result dictionary with:
                - failed: True on non-zero return code.
                - changed: True if enabling succeeded.
                - msg: Human-readable outcome message or stdout on failure.

        Notes:
            This uses the `occ` group's enabling flags (`--groups`) where supported.
        """
        # self.module.log(f"NextcloudApps::enable_app({app_name}, {groups})")

        args = self._build_args("app:enable", "--no-ansi", app_name)

        for g in groups or []:
            args.append("--groups")
            args.append(g)

        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            return dict(failed=False, changed=True, msg="App was successfully enabled.")

        return dict(failed=True, changed=False, msg=self._best_error(out, err))

    def disable_app(self, app_name: str) -> Dict[str, Any]:
        """
        Disable a Nextcloud app via `occ app:disable`.

        Command executed:
            occ app:disable --no-ansi <app_name>

        Args:
            app_name: The Nextcloud app identifier.

        Returns:
            An Ansible-style result dictionary with:
                - failed: True on non-zero return code.
                - changed: True if disabling succeeded.
                - msg: Human-readable outcome message or stdout on failure.
        """
        # self.module.log(f"NextcloudApps::disable_app({app_name})")

        args = self._build_args("app:disable", "--no-ansi", app_name)
        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            return dict(
                failed=False, changed=True, msg="App was successfully disabled."
            )

        return dict(failed=True, changed=False, msg=self._best_error(out, err))

    def app_settings(
        self, app_name: str, app_settings: Mapping[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply app-specific configuration values via `occ config:app:set`.

        Example commands (illustrative):
            occ config:app:set --no-ansi --output json --value yes <app> <key>

        Args:
            app_name: The Nextcloud app identifier, e.g. "richdocuments".
            app_settings: Mapping of config keys to values. Supported value types:
                - bool: converted to "yes"/"no"
                - str: passed as-is
                Any other type is ignored (and logged).

        Returns:
            An Ansible-style result dictionary containing:
                - changed (bool): Aggregated change state across applied keys.
                - failed (bool): Aggregated failure state across applied keys.
                - msg (list): Per-key results as a list of dictionaries.

        Notes:
            - The method uses `--output json`, but the current implementation does not
              parse the JSON output; it only checks the return code.
            - Aggregation uses the `results()` helper from `module_results`.
        """
        """
                sudo --preserve-env --user www-data
                    php occ config:app:get
                        richdocuments disable_certificate_verification
                sudo --preserve-env --user www-data
                    php occ config:app:set
                        --output json --value yes --update-only richdocuments disable_certificate_verification
            """
        # self.module.log(f"NextcloudApps::app_settings({app_name}, {app_settings})")

        result_state: List[Dict[str, Any]] = []
        any_changed = False
        any_failed = False

        for config_key, config_value in app_settings.items():
            desired_is_bool = isinstance(config_value, bool)

            if desired_is_bool:
                desired_str = "yes" if config_value else "no"
            elif isinstance(config_value, str):
                desired_str = config_value
            else:
                # Avoid logging raw values (could be sensitive); log only type + key.
                # self.module.log(
                #     msg=f"ignore non-string value for key {config_key} (type={type(config_value).__name__})"
                # )
                continue

            # 1) Read current value to make the operation idempotent.
            rc_get, current_value, get_msg = self._get_app_config_value(
                app_name, config_key
            )

            already_desired = False
            if rc_get == 0 and current_value is not None:
                if desired_is_bool:
                    cur_bool = self._parse_boolish(current_value)
                    des_bool = bool(config_value)
                    if cur_bool is not None:
                        already_desired = cur_bool == des_bool
                    else:
                        already_desired = current_value.strip() == desired_str.strip()
                else:
                    already_desired = current_value.strip() == desired_str.strip()

            if already_desired:
                changed = False
                failed = False
                msg = f"config value for {config_key} is already set."
            else:
                # 2) Apply only if needed (or if reading current state failed).
                args: List[str] = []
                args += self.occ_base_args
                args.append("config:app:set")
                args.append("--no-ansi")
                args.append("--output")
                args.append("json")
                args.append("--value")
                args.append(desired_str)
                args.append(app_name)
                args.append(config_key)

                rc_set, out_set, err_set = self._exec(args, check_rc=False)

                if rc_set == 0:
                    failed = False
                    changed = True
                    msg = f"config value for {config_key} was successfully set."
                else:
                    failed = True
                    changed = False
                    msg = (
                        out_set.strip()
                        or err_set.strip()
                        or get_msg
                        or "Failed to set config value."
                    )

            any_changed = any_changed or changed
            any_failed = any_failed or failed

            # Per-key result entry (keeps msg list structure and adds key context)
            res: Dict[str, Any] = {}
            res[app_name] = dict(
                key=config_key, changed=changed, failed=failed, msg=msg
            )
            result_state.append(res)

        return dict(changed=any_changed, failed=any_failed, msg=result_state)

    def list_apps(self) -> Tuple[Dict[str, Any], List[str], List[str]]:
        """
        List installed apps and their enabled/disabled state via `occ app:list`.

        Command executed:
            occ app:list --no-ansi --output json

        Returns:
            Tuple of:
                - app_names (dict): Parsed JSON output, typically containing
                  "enabled" and "disabled" mappings.
                - enabled_apps (list[str]): App identifiers that are enabled.
                - disabled_apps (list[str]): App identifiers that are disabled.

        Notes:
            The exact JSON schema depends on the Nextcloud version. The method expects
            top-level keys "enabled" and "disabled" that are mapping-like.
        """
        # self.module.log("NextcloudApps::list_apps()")

        app_names: Dict[str, Any] = {}

        args = self._build_args("app:list", "--no-ansi", "--output", "json")
        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            try:
                app_names = json.loads(out)
            except json.JSONDecodeError as e:
                self.module.log(
                    msg=f"Failed to parse occ JSON output in list_apps(): {e}"
                )
                app_names = {}

        enabled_apps = [x for x, _ in app_names.get("enabled", {}).items()]
        disabled_apps = [x for x, _ in app_names.get("disabled", {}).items()]

        return (app_names, enabled_apps, disabled_apps)

    def check_for_updates(
        self, check_installed: bool = False
    ) -> Tuple[int, bool, Dict[str, str], str]:
        """
        Check for available app updates via `occ update:check`.

        Command executed:
            occ update:check --no-ansi

        Args:
            check_installed: Currently unused. Kept for API compatibility.

        Returns:
            Tuple of:
                - rc (int): Command return code.
                - update (bool): True if at least one update is available.
                - res (dict[str,str]): Mapping of app name -> target version for updates.
                - err (str): Stderr output.

        Parsing:
            This method parses stdout with a regex matching lines like:
                "Update for <app> to version <version> is available"

        Notes:
            Nextcloud output may change across versions; adjust the regex if needed.
        """
        # self.module.log(f"NextcloudApps::check_for_updates({check_installed})")

        res: Dict[str, str] = {}

        args = self._build_args("update:check", "--no-ansi")
        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            for match in _UPDATE_AVAILABLE_RE.finditer(out):
                app, version = match.groups()
                res[app] = version

        update = bool(res)
        return (rc, update, res, err)

    def update_app(self, app_name: str) -> Tuple[int, str, str]:
        """
        Update a single app via `occ app:update`.

        Command executed:
            occ app:update --no-ansi <app_name>

        Args:
            app_name: The Nextcloud app identifier.

        Returns:
            Tuple of:
                - rc (int): Command return code.
                - out (str): Stdout output.
                - err (str): Stderr output.

        Notes:
            This method does not interpret stdout/stderr beyond returning them.
            Callers typically decide "changed" based on rc and/or output content.
        """
        # self.module.log(f"NextcloudApps::update_app({app_name})")

        args = self._build_args("app:update", "--no-ansi", app_name)
        rc, out, err = self._exec(args, check_rc=False)

        return (rc, out, err)

    @staticmethod
    def _parse_boolish(value: str) -> Optional[bool]:
        """
        Best-effort parser for boolean-like strings returned by `occ`.

        Returns:
            True/False if the value can be interpreted as boolean, otherwise None.
        """
        v = value.strip().lower()
        if v in {"1", "true", "yes", "on"}:
            return True
        if v in {"0", "false", "no", "off"}:
            return False
        return None

    def _get_app_config_value(
        self, app_name: str, key: str
    ) -> Tuple[int, Optional[str], str]:
        """
        Read an app config value via `occ config:app:get`.

        Returns:
            (rc, value, message)
            - rc: return code from occ
            - value: stdout stripped if rc == 0, else None
            - message: best-effort message from stdout/stderr
        """
        args: List[str] = []
        args += self.occ_base_args
        args.append("config:app:get")
        args.append("--no-ansi")
        args.append(app_name)
        args.append(key)

        rc, out, err = self._exec(args, check_rc=False)
        msg = out.strip() or err.strip()

        if rc == 0:
            return rc, out.strip(), msg

        return rc, None, msg
