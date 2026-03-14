#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0


"""
identities.py

Nextcloud identity management helpers for Ansible modules, implemented via the `occ` CLI.

This module provides :class:`NextcloudIdentity`, a convenience wrapper around Nextcloud's
`occ` subcommands related to users and groups. It inherits from :class:`Occ` to reuse the
prepared command base (`occ_base_args`) and the execution helper (`_exec`).

Supported operations
--------------------
- List users and groups (JSON output)
- Create and remove users
- Reset user passwords (via `--password-from-env` and `OC_PASS`)
- Read user information (JSON output)
- Manage group membership for users
- Create and remove groups
- Apply per-user settings via `occ user:setting`

Execution model
---------------
All commands are executed using `AnsibleModule.run_command()` via the parent `Occ` class.
If `sudo` is used inside `occ_base_args`, environment propagation (e.g. `OC_PASS`) depends
on `sudoers` configuration (e.g. `--preserve-env=OC_PASS`).

Security note
-------------
Passwords may be passed through environment variables (OC_PASS). Avoid logging sensitive
values in production environments.
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


class NextcloudIdentity(Occ):
    """
    High-level user and group management wrapper for Nextcloud using the `occ` CLI.

    This class extends :class:`Occ` and provides convenience methods for managing
    identities in Nextcloud: users, groups, membership, and user settings.

    Attributes:
        module: Ansible module instance providing `run_command()` and `log()`.
        owner: OS user used to execute `occ` (typically "www-data").
        working_dir: Nextcloud installation directory that contains the `occ` script.
        existing_users: Cached list of existing user ids (populated by :meth:`identities`).
        existing_groups: Cached list of existing group ids (populated by :meth:`identities`).

    Notes:
        - Several methods return Ansible-style dicts: `{"failed": bool, "changed": bool, "msg": str}`.
        - Some methods return tuples for control flow and aggregation by the caller.
    """

    module: Any = None

    def __init__(self, module: Any, owner: str, working_dir: str) -> None:
        """
        Initialize the identity helper.

        Args:
            module: Ansible module instance providing `run_command()` and `log()`.
            owner: OS user that should run `occ` (commonly "www-data").
            working_dir: Nextcloud installation directory (contains `occ`).

        Side effects:
            Calls :class:`Occ` initializer to configure the base `occ` command vector.
        """
        super().__init__(
            module, owner, working_dir
        )  # Ruft den Konstruktor der Basisklasse Occ auf

        self.module = module

        # self.module.log(f"NextcloudIdentity::__init__({owner}, {working_dir})")

        self.owner = owner
        self.working_dir = working_dir

        # Ensure attributes exist even if identities() was not called yet.
        self.existing_users: List[str] = []
        self.existing_groups: List[str] = []

    # ---- private helpers (no public API changes) ----

    def _build_args(self, *parts: str) -> List[str]:
        return [*self.occ_base_args, *parts]

    @staticmethod
    def _best_error(out: str, err: str) -> str:
        return (out or "").strip() or (err or "").strip()

    @staticmethod
    def _redact_mapping(data: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Redact common secret-like keys for logging only.
        """
        redacted: Dict[str, Any] = {}
        for k, v in data.items():
            if str(k).lower() in {"password", "pass", "secret", "token"}:
                redacted[k] = "<redacted>"
            else:
                redacted[k] = v
        return redacted

    @staticmethod
    def _normalize_value_for_compare(value: Any) -> str:
        """
        Normalize values to strings for idempotence comparisons.
        """
        if value is None:
            return ""

        if isinstance(value, bool):
            # Keep boolean normalization conservative; Nextcloud may store as 'true/false' or '1/0'.
            return "true" if value else "false"

        if isinstance(value, str):
            value = value.lower()

        return str(value).strip()

    @staticmethod
    def _looks_like_already_exists(msg: str) -> bool:
        m = msg.lower()
        return "already exists" in m

    @staticmethod
    def _looks_like_missing(msg: str) -> bool:
        m = msg.lower()
        return "does not exist" in m or "not exist" in m or "not found" in m

    def __get_user_setting_value(
        self, username: str, app: str, key: str
    ) -> Optional[str]:
        """
        Best-effort read of a user setting.

        Some Nextcloud versions may support:
            occ user:setting <uid> <app> <key>
        (without a value argument) to print the current value.

        If unsupported, this returns None and callers should fall back to "set".
        """
        # self.module.log(f"NextcloudIdentity::__get_user_setting_value(username: {username}, app: {app}, key: {key})")

        args = self._build_args(
            "user:setting",
            "--no-ansi",
            "--output",
            "json",
            username,
            app,
            key,
        )
        rc, out, err = self._exec(args, check_rc=False)

        if rc != 0:
            return None

        raw = (out or "").strip()
        if not raw:
            return None

        # Try to parse JSON output, but tolerate plain values too.
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                # Common shapes:
                # {"settings": {"email": "x"}} or {"email": "x"}
                if (
                    app in parsed
                    and isinstance(parsed.get(app), dict)
                    and key in parsed[app]
                ):
                    return str(parsed[app][key]).strip()
                if key in parsed:
                    return str(parsed[key]).strip()

        except Exception:
            pass

        return raw

    def identities(self) -> Tuple[List[str], List[str]]:
        """
        Collect and cache existing users and groups.

        Returns:
            Tuple of `(existing_users, existing_groups)`:
                - existing_users: list of user ids
                - existing_groups: list of group ids

        Side effects:
            Populates `self.existing_users` and `self.existing_groups`.
        """
        # self.module.log("NextcloudIdentity::identities()")

        self.existing_users = self.list_users()
        self.existing_groups = self.list_groups()

        return (self.existing_users, self.existing_groups)

    def create_user(self, user_data: dict = {}) -> dict:
        """
        Create a Nextcloud user via `occ user:add`.

        Command executed (conceptual):
            occ user:add [--password-from-env] [--display-name <name>] --no-ansi <uid>

        Args:
            user_data: User specification dictionary. Supported keys:
                - name (str): user id / uid (required)
                - display_name (str): display name (optional)
                - password (str): password for the user (optional; passed via `OC_PASS`)

        Returns:
            An Ansible-style result dictionary:
                - failed (bool): True on error
                - changed (bool): True if the user was created
                - msg (str): status message or stdout on failure

        Notes:
            When `password` is provided, `--password-from-env` is used and `OC_PASS` is
            set via `environ_update` for the process.
        """
        # safe_log = self._redact_mapping(user_data or {})
        # self.module.log(f"NextcloudIdentity::create_user({safe_log})")

        _failed = True
        _changed = False
        _msg = ""

        env: Dict[str, str] = {}

        name = (user_data or {}).get("name", None)
        display_name = (user_data or {}).get("display_name", None)
        password = (user_data or {}).get("password", None)

        if not name:
            return dict(failed=True, changed=False, msg="Missing required user name.")

        args: List[str] = []
        args += self.occ_base_args

        args.append("user:add")

        if password:
            env["OC_PASS"] = str(password)
            args.append("--password-from-env")

        if display_name:
            args.append("--display-name")
            args.append(display_name)

        args.append("--no-ansi")
        args.append(name)

        rc, out, err = self._exec(args, environ_update=env, check_rc=False)

        if rc == 0:
            _msg = "User was successfully created."
            _failed = False
            _changed = True
        else:
            _failed = True
            _changed = False
            _msg = self._best_error(out, err)

        # self.module.log(f"= msg: {_msg}")

        return dict(failed=_failed, changed=_changed, msg=_msg)

    def reset_password(self, user_data: dict = {}) -> dict:
        """
        Reset an existing user's password via `occ user:resetpassword`.

        Command executed (conceptual):
            occ user:resetpassword --no-ansi [--password-from-env] <uid>

        Args:
            user_data: User specification dictionary. Supported keys:
                - name (str): user id / uid (required)
                - password (str): new password (optional; expected via `OC_PASS`)

        Returns:
            An Ansible-style result dictionary:
                - failed (bool): True on error
                - changed (bool): True if password reset succeeded
                - msg (str): stdout/stderr based status message

        Notes:
            This method currently sets `self.module.run_command_environ_update` when a
            password is provided. If your execution relies on `sudo`, make sure that
            `OC_PASS` is preserved/propagated to the `occ` process.
        """
        # safe_log = self._redact_mapping(user_data or {})
        # self.module.log(f"NextcloudIdentity::reset_password({safe_log})")

        _failed = True
        _changed = False
        _msg = ""

        name = (user_data or {}).get("name", None)
        password = (user_data or {}).get("password", None)

        if not name:
            return dict(failed=True, changed=False, msg="Missing required user name.")

        env: Dict[str, str] = {}

        args = []
        args += self.occ_base_args

        args.append("user:resetpassword")
        args.append("--no-ansi")

        if password:
            # IMPORTANT: pass via environ_update (fixes the previous "env not propagated" issue)
            env["OC_PASS"] = str(password)
            args.append("--password-from-env")

        args.append(name)

        rc, out, err = self._exec(args, environ_update=env or None, check_rc=False)

        if rc == 0:
            _msg = f"{out.strip()}."
            _failed = False
            _changed = True
        else:
            _failed = True
            _changed = False
            _msg = f"{self._best_error(out, err)}."

        return dict(failed=_failed, changed=_changed, msg=_msg)

    def remove_user(self, name: str) -> dict:
        """
        Delete a Nextcloud user via `occ user:delete`.

        Command executed:
            occ user:delete --no-ansi <uid>

        Args:
            name: User id / uid to delete.

        Returns:
            An Ansible-style result dictionary:
                - failed (bool)
                - changed (bool)
                - msg (str)
        """

        # self.module.log(f"NextcloudIdentity::remove_user({name})")

        _failed = True
        _changed = False
        _msg = ""

        if not name:
            return dict(failed=True, changed=False, msg="Missing required user name.")

        args = []
        args += self.occ_base_args

        args.append("user:delete")
        args.append("--no-ansi")
        args.append(name)

        # self.module.log(f" args: '{args}'")

        rc, out, err = self._exec(args, check_rc=False)

        # self.module.log(f" rc : '{rc}'")
        # self.module.log(f" out: {type(out)} - '{out.strip()}'")
        # self.module.log(f" err: {type(err.strip())} - '{err.strip()}'")

        if rc == 0:
            _msg = "User was successfully removed."
            _failed = False
            _changed = True
        else:
            msg = self._best_error(out, err)
            if self._looks_like_missing(msg):
                _failed = False
                _changed = False
                _msg = msg
            else:
                _failed = True
                _changed = False
                _msg = msg

        return dict(failed=_failed, changed=_changed, msg=_msg)

    def list_users(self) -> List[str]:
        """
        List all Nextcloud users via `occ user:list`.

        Command executed:
            occ user:list --no-ansi --output json

        Returns:
            List of user ids (uids).

        Raises:
            Any JSON parsing errors will propagate if `occ` returns invalid JSON.
        """
        # self.module.log("NextcloudIdentity::list_users()")

        args = []
        args += self.occ_base_args

        args.append("user:list")
        args.append("--no-ansi")
        args.append("--output")
        args.append("json")

        rc, out, err = self._exec(args, check_rc=False)

        try:
            parsed = json.loads(out)
        except Exception as e:
            self.module.log(msg=f"Failed to parse occ JSON output in list_users(): {e}")
            raise

        if isinstance(parsed, dict):
            user_names = [x for x, _ in parsed.items()]
        elif isinstance(parsed, list):
            user_names = [str(x) for x in parsed]
        else:
            user_names = []

        # self.module.log(f"= users: {user_names}")

        return user_names

    def user_settings(
        self, username: str, user_settings: list
    ) -> Tuple[bool, bool, str]:
        """
        Apply per-user settings using `occ user:setting`.

        This method iterates over a list of app setting objects and calls
        :meth:`add_user_settings` for each key/value pair.

        Args:
            username: Target user id / uid.
            user_settings: List of structures shaped like:
                [
                  {"settings": {"display_name": "...", "email": "..."}},
                  {"another_app": {"key": "value"}}
                ]

        Returns:
            Tuple `(failed, changed, msg)`.

        Notes:
            The current implementation builds an internal result array but does not
            aggregate it into a final `(failed, changed, msg)` outcome yet; it returns
            default values. Typically, callers should enhance this method to compute
            `changed` and `failed` based on `add_user_settings()` results.
        """
        # self.module.log(
        #     f"NextcloudIdentity::user_settings({username}, {user_settings})"
        # )

        _failed = False
        _changed = False
        _msg = ""

        if not user_settings:
            return (_failed, _changed, "No user settings to apply.")

        changed_count = 0
        skipped_count = 0
        failed_count = 0

        # Keep existing internal structure for debugging, but also compute real result flags.
        result_arr: List[Dict[str, Any]] = []

        for app_setting in user_settings:
            # self.module.log(f"- {app_setting}")
            if not isinstance(app_setting, dict):
                continue

            for app, settings in app_setting.items():
                result: Dict[str, Any] = {app: {}}
                # self.module.log(f"  {app}:  ({settings} - {type(settings)})")

                if not isinstance(settings, dict):
                    continue

                for key, value in settings.items():
                    # self.module.log(f"    - {key}: {value}")

                    # Best-effort idempotence: read current value if supported.
                    current = self.__get_user_setting_value(username, app, key)
                    desired = self._normalize_value_for_compare(value)

                    if current is not None:
                        current = self._normalize_value_for_compare(current)

                    # self.module.log(f"      current: {current} - type: {type(current)}")
                    # self.module.log(f"      desired: {desired} - type: {type(desired)}")

                    if current == desired:
                        result[app][key] = True
                        skipped_count += 1
                        continue

                    ok = self.add_user_settings(
                        username=username, app=app, key=key, value=value
                    )
                    result[app][key] = ok

                    if ok:
                        changed_count += 1
                    else:
                        failed_count += 1

                result_arr.append(result)

        # self.module.log(f"    - {result_arr}")

        _failed = failed_count > 0
        _changed = changed_count > 0

        parts: List[str] = []
        if changed_count:
            parts.append(f"Applied {changed_count} setting(s).")
        if skipped_count:
            parts.append(f"Skipped {skipped_count} setting(s) (already set).")
        if failed_count:
            parts.append(f"Failed {failed_count} setting(s).")

        _msg = " ".join(parts) if parts else "No settings applied."

        return (_failed, _changed, _msg)

    def user_info(self, username: str) -> Dict[str, Any]:
        """
        Retrieve user information via `occ user:info`.

        Command executed:
            occ user:info --no-ansi --output json <uid>

        Args:
            username: User id / uid to query.

        Returns:
            A dictionary describing the user state:
                - if present: JSON payload from `occ` plus `{"state": "present"}`
                - if absent or error: `{"user_id": <uid>, "state": "absent", "msg": <reason>}`
        """

        # self.module.log(f"NextcloudIdentity::user_info({username})")

        args = []
        args += self.occ_base_args

        args.append("user:info")
        args.append("--no-ansi")
        args.append("--output")
        args.append("json")
        args.append(username)

        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            out = json.loads(out)
            out.update({"state": "present"})
        else:
            out = dict(user_id=username, state="absent", msg=self._best_error(out, err))

        return out

    def add_user_to_group(self, username: str, groups: Sequence[str]) -> List[str]:
        """
        Add a user to one or more groups via `occ group:adduser`.

        Args:
            username: User id / uid.
            groups: Iterable of group ids.

        Returns:
            List of groups the user was successfully added to.
        """
        # self.module.log(f"NextcloudIdentity::user_to_group({username}, {groups})")

        _group_added: List[str] = []
        for group in groups:
            args = self._build_args("group:adduser", "--no-ansi", group, username)
            rc, out, err = self._exec(args, check_rc=False)

            if rc == 0:
                _group_added.append(group)

        # self.module.log(f"= {_group_added}")
        return _group_added

    def delete_user_from_group(self, username: str, groups: Sequence[str]) -> List[str]:
        """
        Remove a user from one or more groups via `occ group:removeuser`.

        Args:
            username: User id / uid.
            groups: Iterable of group ids.

        Returns:
            List of groups the user was successfully removed from.
        """
        # self.module.log(
        #     f"NextcloudIdentity::delete_user_from_group({username}, {groups})"
        # )
        _group_removed: List[str] = []

        for group in groups:
            args = self._build_args("group:removeuser", "--no-ansi", group, username)
            rc, out, err = self._exec(args, check_rc=False)

            if rc == 0:
                _group_removed.append(group)

        # self.module.log(f"= {_group_removed}")
        return _group_removed

    def add_user_settings(self, username: str, app: str, key: str, value: Any) -> bool:
        """
        Set a single user setting via `occ user:setting`.

        Command executed:
            occ user:setting --no-ansi --output json <uid> <app> <key> <value>

        Args:
            username: User id / uid.
            app: App namespace (e.g. "settings").
            key: Setting key.
            value: Setting value. Will be converted to string.

        Returns:
            True if the command succeeded (rc == 0), otherwise False.

        Notes:
            On failure, the method logs the stdout output for diagnostics.
        """
        # self.module.log(
        #     f"NextcloudIdentity::add_user_settings({username}, {app}, {key}, {value})"
        # )

        args = []
        args += self.occ_base_args

        args.append("user:setting")
        args.append("--no-ansi")
        args.append("--output")
        args.append("json")
        args.append(username)
        args.append(app)
        args.append(key)
        args.append(str(value))

        rc, out, err = self._exec(args, check_rc=False)

        if rc == 0:
            return True

        # self.module.log(f"__add_user_settings({username}, {app}, {key}, {value})")
        self.module.log(f"WARNING: {self._best_error(out, err)}")
        return False

    def list_groups(self) -> List[str]:
        """
        List all Nextcloud groups via `occ group:list`.

        Command executed:
            occ group:list --no-ansi --output json

        Returns:
            List of group ids.

        Raises:
            Any JSON parsing errors will propagate if `occ` returns invalid JSON.
        """
        # self.module.log("NextcloudIdentity::list_groups()")

        args = []
        args += self.occ_base_args

        args.append("group:list")
        args.append("--no-ansi")
        args.append("--output")
        args.append("json")

        rc, out, err = self._exec(args, check_rc=False)

        try:
            parsed = json.loads(out)
        except Exception as e:
            self.module.log(
                msg=f"Failed to parse occ JSON output in list_groups(): {e}"
            )
            raise

        if isinstance(parsed, dict):
            group_names = [x for x, _ in parsed.items()]
        elif isinstance(parsed, list):
            group_names = [str(x) for x in parsed]
        else:
            group_names = []

        # self.module.log(f"= groups: {group_names}")

        return group_names

    def user_groups(
        self, username: str, groups: Sequence[str]
    ) -> Tuple[bool, bool, str]:
        """
        Ensure a user is a member of exactly the requested group set.

        This method:
        - verifies the user exists
        - computes missing groups (to add) and extra groups (to remove)
        - skips invalid/non-existing groups (based on `self.existing_groups`)
        - performs adds/removals via `group:adduser` and `group:removeuser`

        Args:
            username: User id / uid.
            groups: Desired group ids for the user.

        Returns:
            Tuple `(failed, changed, msg)`:
                - failed: False if operations were executed successfully or only skipped
                - changed: True if any membership changes were applied
                - msg: Summary message (added/removed/skipped)

        Preconditions:
            `self.existing_groups` should be populated (e.g. via :meth:`identities`).
        """
        # self.module.log(f"NextcloudIdentity::user_groups({username}, {groups})")

        _failed = True
        _changed = False
        _msg = ""

        # Ensure we have a group cache even if identities() wasn't called.
        if not getattr(self, "existing_groups", None):
            self.existing_groups = self.list_groups()

        _state = self.user_info(username)
        user_state = _state.get("state", "absent")

        if user_state == "absent":
            return (_failed, _changed, f"The User {username} has not yet been created.")

        # user is current in groups
        user_groups = _state.get("groups", [])

        # invalid groups
        groups_invalid = list(set(groups) - set(self.existing_groups))

        # valid groups for this user, remove not exists groups
        valid_user_groups = [x for x in self.existing_groups if x in groups]

        # user ist NOT in group
        groups_missing = [x for x in valid_user_groups if x not in user_groups]

        # user should removed from group
        groups_removing = [x for x in user_groups if x not in groups]

        # self.module.log(f"{username} : {user_state}")
        # self.module.log(f"  - groups exists: {self.existing_groups}")
        # self.module.log(f"    - is in groups: {user_groups}")
        # self.module.log(f"    - should in groups: {groups}")
        # self.module.log(f"    - valid user groups: {valid_user_groups}")
        # self.module.log(f"    - groups missing: {groups_missing}")
        # self.module.log(f"    - remove from groups: {groups_removing}")
        # self.module.log(f"    - groups invalid: {groups_invalid}")
        _group_added: List[str] = []
        _group_removed: List[str] = []
        _group_skipped = groups_invalid
        m: List[str] = []

        if len(groups_missing) > 0:
            _group_added = self.add_user_to_group(
                username=username, groups=groups_missing
            )

        if len(groups_removing) > 0:
            _group_removed = self.delete_user_from_group(
                username=username, groups=groups_removing
            )

        if len(_group_removed) > 0 or len(_group_added) > 0:
            _failed = False
            _changed = True

            if len(_group_added) > 0:
                added = ", ".join(_group_added)
                m.append(f" Added to group(s): {added}.")

            if len(_group_removed) > 0:
                removed = ", ".join(_group_removed)
                m.append(f" Removed from group(s): {removed}.")

        if len(_group_skipped) > 0:
            skipped = ", ".join(_group_skipped)
            m.append(f"Group(s) {skipped} does not exist, was skipped.")

        _msg = " ".join(m)

        return (_failed, _changed, _msg)

    def create_group(self, name: str, display_name: Optional[str] = None) -> dict:
        """
        Create a Nextcloud group via `occ group:add`.

        Command executed (conceptual):
            occ group:add --no-ansi [--display-name <display_name>] <group_id>

        Args:
            name: Group id to create.
            display_name: Optional group display name.

        Returns:
            An Ansible-style result dictionary:
                - failed (bool)
                - changed (bool)
                - msg (str)

        Notes:
            On failure, the method matches certain known output patterns (e.g. group exists)
            and returns that message.
        """

        # self.module.log(f"NextcloudIdentity::create_group({name}, {display_name})")
        _failed = True
        _changed = False

        args = []
        args += self.occ_base_args

        args.append("group:add")
        args.append("--no-ansi")
        # args.append("--output")
        # args.append("json")

        if display_name:
            args.append("--display-name")
            args.append(display_name)

        args.append(name)

        # self.module.log(f" args: '{args}'")

        rc, out, err = self._exec(args, check_rc=False)

        # self.module.log(f" rc : '{rc}'")
        # self.module.log(f" out: {type(out)} - '{out.strip()}'")
        # self.module.log(f" err: {type(err.strip())} - '{err.strip()}'")

        if rc == 0:
            _msg = "Group was successfully created."
            _failed = False
            _changed = True
        else:
            patterns = [
                'Group ".*" already exists.',
            ]
            error = None

            for pattern in patterns:
                filter_list = list(
                    filter(lambda x: re.search(pattern, x), out.splitlines())
                )
                if len(filter_list) > 0 and isinstance(filter_list, list):
                    error = (filter_list[0]).strip()
                    self.module.log(f"  - {error}")
                    break
            # self.module.log("--------------------")

            msg = error or self._best_error(out, err)

            if self._looks_like_already_exists(msg):
                _failed = False
                _changed = False
                _msg = msg or f"Group {name} already created."
            else:
                _failed = True
                _changed = False
                _msg = msg

        return dict(failed=_failed, changed=_changed, msg=_msg)

    def remove_group(self, name: str) -> dict:
        """
        Delete a Nextcloud group via `occ group:delete`.

        Command executed:
            occ group:delete --no-ansi <group_id>

        Args:
            name: Group id to delete.

        Returns:
            An Ansible-style result dictionary:
                - failed (bool)
                - changed (bool)
                - msg (str)

        Notes:
            The current pattern matching list contains a message ("already exists") that
            does not fit deletion; it is preserved to reflect the existing behavior.
        """
        # self.module.log(f"NextcloudIdentity::remove_group({name})")
        _failed = True
        _changed = False

        args = []
        args += self.occ_base_args

        args.append("group:delete")
        args.append("--no-ansi")
        args.append(name)

        # self.module.log(f" args: '{args}'")

        rc, out, err = self._exec(args, check_rc=False)

        # self.module.log(f" rc : '{rc}'")
        # self.module.log(f" out: {type(out)} - '{out.strip()}'")
        # self.module.log(f" err: {type(err.strip())} - '{err.strip()}'")

        if rc == 0:
            _msg = "Group was successfully removed."
            _failed = False
            _changed = True
        else:
            patterns = [
                'Group ".*" already exists.',
            ]
            error = None

            for pattern in patterns:
                filter_list = list(
                    filter(lambda x: re.search(pattern, x), out.splitlines())
                )
                if len(filter_list) > 0 and isinstance(filter_list, list):
                    error = (filter_list[0]).strip()
                    self.module.log(f"  - {error}")
                    break
            # self.module.log("--------------------")

            msg = error or self._best_error(out, err)

            if self._looks_like_missing(msg):
                _failed = False
                _changed = False
                _msg = msg
            else:
                _failed = True
                _changed = False
                _msg = msg

        return dict(failed=_failed, changed=_changed, msg=_msg)
