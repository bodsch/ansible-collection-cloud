# python 3 headers, required if submitting to Ansible
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import os
import re
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from ansible.utils.display import Display

display = Display()


class FilterModule(object):
    """
    Ansible Jinja2 filter plugin for Nextcloud-related data structures.

    This plugin provides convenience filters used in roles/playbooks to:
    - Extract directory paths from a Nextcloud configuration mapping.
    - Determine configured cache backends (Redis/Memcache) from configuration data.
    - Map a configured database type to required OS packages.
    - Validate passwords for Nextcloud user definitions against a given policy.
    """

    def filters(self) -> Dict[str, Any]:
        """
        Return the filter mapping exposed to Jinja2.

        Returns:
            Mapping of filter name to callable.
        """
        return {
            "directories": self.directories,
            "nc_directories": self.directories,
            "nc_configured_cache": self.configured_cache,
            "nc_database_driver": self.configured_database,
            "nc_validate_passwords": self.validate_passwords,
            "nc_php_module_name": self.php_module_name,
        }

    def directories(self, data: Mapping[str, Any]) -> List[str]:
        """
        Extract relevant directory paths from a Nextcloud configuration mapping.

        Expected input shape (simplified):
            skeleton_directory: "/path"
            template_directory: "/path"
            temp_directory: "/path"
            update_directory: "/path"
            data_directory: "/path"
            logging:
              file: "/var/log/nextcloud/nextcloud.log"
              logfile_audit: "/var/log/nextcloud/audit.log"
            apps:
              paths:
                - path: "/var/www/nextcloud/apps"
                - path: "/var/www/nextcloud/custom_apps"

        Behavior (kept compatible with previous implementation):
            - Collects values of specific top-level directory keys.
            - Adds directory name of logging.file (only "file", not "logfile_audit").
            - Adds app paths from apps.* items where a dict key "path" exists.
            - Removes duplicates and empty values, sorts ascending.

        Args:
            data: Configuration mapping.

        Returns:
            A sorted list of unique directory paths (strings).
        """
        display.vv(f"bodsch.cloud.directories(data: {data})")

        dirs: List[str] = []

        if not isinstance(data, Mapping):
            display.vv("= return : []")
            return []

        directory_keys = {
            "skeleton_directory",
            "template_directory",
            "temp_directory",
            "update_directory",
            "data_directory",
        }

        # Keep behavior: take values as provided and filter out empty entries later.
        for key, value in data.items():
            if key in directory_keys and isinstance(value, str):
                dirs.append(value)

        # Keep behavior: only consider logging.file (not logfile_audit)
        logging_section = data.get("logging")
        if isinstance(logging_section, Mapping):
            log_file = logging_section.get("file")
            if isinstance(log_file, str):
                dirs.append(os.path.dirname(log_file))

        # Keep behavior: collect "path" entries from apps section
        apps_section = data.get("apps")
        if isinstance(apps_section, Mapping):
            for _k, apps_list in apps_section.items():
                if not isinstance(apps_list, list):
                    continue
                for app_item in apps_list:
                    if not isinstance(app_item, Mapping):
                        continue
                    p = app_item.get("path")
                    if isinstance(p, str):
                        dirs.append(p)

        # Deduplicate + remove empty + sort
        unique_dirs = list(set(dirs))
        unique_dirs = list(filter(None, unique_dirs))
        unique_dirs.sort(reverse=False)

        display.vv(f"= return : {unique_dirs}")

        return unique_dirs

    def configured_cache(self, data: Any, cache: str = "redis") -> List[Dict[str, Any]]:
        """
        Filter configured cache backend entries.

        Supported cache types:
            - "redis": expects `data` as a list of dicts, returns entries having a "host".
            - "memcache": expects `data` as a dict with key "servers" containing list[dict],
              returns server entries having a "host".

        Args:
            data: Cache configuration data (shape depends on `cache`).
            cache: Cache backend type ("redis" or "memcache").

        Returns:
            A list of configuration dicts for the requested cache type.
            For unknown cache types, returns an empty list (instead of raising).
        """
        display.vv(f"bodsch.cloud.configured_cache(data: {data}, cache: {cache})")

        result: List[Dict[str, Any]] = []

        if cache == "redis":
            if isinstance(data, Sequence):
                for item in data:
                    if isinstance(item, Mapping) and item.get("host", None):
                        result.append(dict(item))
        elif cache == "memcache":
            if isinstance(data, Mapping):
                memcache_servers = data.get("servers", [])
                if isinstance(memcache_servers, list):
                    for item in memcache_servers:
                        if isinstance(item, Mapping) and item.get("host", None):
                            result.append(dict(item))

        display.vv(f"- result : {result}")

        return result

    def configured_database(
        self, data: Mapping[str, Any], packages: Mapping[str, Any]
    ) -> Any:
        """
        Determine required packages for a configured database type.

        Args:
            data: Database configuration mapping containing at least "type".
            packages: Mapping of database type -> package list (or any value).

        Returns:
            The package mapping entry for the configured database type, or an empty list
            if the type is unknown. Return type is kept compatible with the previous
            implementation (may be list or any object).
        """
        display.vv(
            f"bodsch.cloud.configured_database(data: {data}, packages: {packages})"
        )

        database_type = data.get("type") if isinstance(data, Mapping) else None
        package = (
            packages.get(database_type, []) if isinstance(packages, Mapping) else []
        )

        display.vv(f"- result : {package}")

        return package

    def php_module_name(self, data: List[str]) -> List[str]:
        """ """
        display.vv(f"bodsch.cloud.nc_php_module_name(data: {data})")

        result: List[str] = []

        result = [x.replace("php-", "").replace("legacy-", "") for x in data]

        return result

    def validate_passwords(
        self, data: Sequence[Mapping[str, Any]], config: Mapping[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate passwords for user definitions against a policy.

        Input expectations:
            data: list of user dicts, each containing at least:
                - name: str
                - password: str
            config: policy dict with optional keys:
                - upper_and_lower_case: bool
                - special_character: bool
                - numeric_character: bool
                - length: int (minimum length)

        Return format (kept compatible):
            - If any validation errors exist:
                {"failed": True, "result": {"user": {"errors": [..]}}}
            - If all passwords pass:
                {"failed": False}

        Args:
            data: User definitions.
            config: Password policy configuration.

        Returns:
            Validation result dict.
        """
        display.vv(f"bodsch.cloud.validate_passwords(data, config: {config})")

        result: Dict[str, Any] = {}

        # Build username -> password map (robust against missing keys)
        user_data: Dict[str, str] = {}
        for user in data or []:
            if not isinstance(user, Mapping):
                continue
            username = user.get("name")
            if not username:
                continue
            password = user.get("password", "")  # avoid None crashes
            user_data[str(username)] = "" if password is None else str(password)

        for username, password in user_data.items():
            valid_upper_lower = True
            valid_upper_lower_msg = ""
            valid_special_char = True
            valid_special_char_msg = ""
            valid_numeric_char = True
            valid_numeric_char_msg = ""
            valid_length = True
            valid_length_msg = ""

            display.vv(f"  - validate password for '{username}' ... ")

            if config.get("upper_and_lower_case", True):
                valid_upper_lower, valid_upper_lower_msg = (
                    self._validate_upper_and_lower_case(password)
                )

            if config.get("special_character", True):
                valid_special_char, valid_special_char_msg = (
                    self._validate_special_character(password)
                )

            if config.get("numeric_character", True):
                valid_numeric_char, valid_numeric_char_msg = (
                    self._validate_numeric_character(password)
                )

            length_cfg = config.get("length", True)
            if length_cfg:
                # Preserve intent but avoid odd bool-as-int behavior:
                # - if length is True -> use default (10)
                # - if length is int/str -> parse in _validate_length
                min_length = 10 if isinstance(length_cfg, bool) else length_cfg
                valid_length, valid_length_msg = self._validate_length(
                    password, min_length
                )

            if (
                (not valid_upper_lower)
                or (not valid_special_char)
                or (not valid_numeric_char)
                or (not valid_length)
            ):
                validate_msgs = list(
                    filter(
                        None,
                        [
                            valid_upper_lower_msg,
                            valid_special_char_msg,
                            valid_numeric_char_msg,
                            valid_length_msg,
                        ],
                    )
                )
                result[username] = dict(errors=validate_msgs)

        if len(result) > 0:
            return dict(failed=True, result=result)

        return dict(failed=False)

    def _validate_upper_and_lower_case(self, password: str) -> Tuple[bool, str]:
        """
        Validate that `password` contains at least one lower-case and one upper-case letter.

        Args:
            password: Password string.

        Returns:
            Tuple of (is_valid, message). Message is empty when valid.
        """
        valide = False
        msg = (
            "Password needs to contain at least one lower and one upper case character."
        )

        pattern = re.compile(r"^(?=.*[a-z])(?=.*[A-Z]).+$")
        match = re.search(pattern, password)

        if match:
            valide = True
            msg = ""

        return (valide, msg)

    def _validate_special_character(self, password: str) -> Tuple[bool, str]:
        """
        Validate that `password` contains at least one non-alphanumeric character.

        Args:
            password: Password string.

        Returns:
            Tuple of (is_valid, message). Message is empty when valid.
        """
        valide = False
        msg = "Password needs to contain at least one special character."

        # Note: empty string is not alnum, but other checks (length, upper/lower, numeric)
        # will still fail. Behavior is kept compatible.
        if not password.isalnum():
            valide = True
            msg = ""

        return (valide, msg)

    def _validate_numeric_character(self, password: str) -> Tuple[bool, str]:
        """
        Validate that `password` contains at least one numeric digit.

        Args:
            password: Password string.

        Returns:
            Tuple of (is_valid, message). Message is empty when valid.
        """
        valide = False
        msg = "Password needs to contain at least one numeric character."

        pattern = re.compile(r"^(?=.*\d).+$")
        match = re.search(pattern, password)

        if match:
            valide = True
            msg = ""

        return (valide, msg)

    def _validate_length(self, password: str, length: Any = 10) -> Tuple[bool, str]:
        """
        Validate that `password` length is at least `length`.

        Args:
            password: Password string.
            length: Minimum length (int or str convertible to int). Defaults to 10.

        Returns:
            Tuple of (is_valid, message). Message is empty when valid.
        """
        try:
            min_len = int(length)
        except Exception:
            min_len = 10

        valide = False
        msg = f"Password needs to be at least {min_len} characters long."

        if len(password) >= min_len:
            valide = True
            msg = ""

        return (valide, msg)
