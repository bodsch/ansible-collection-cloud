#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2021-2025, Bodo Schulz <bodo@boone-schulz.de>
# BSD 2-clause (see LICENSE or https://opensource.org/licenses/BSD-2-Clause)

from __future__ import absolute_import, print_function
import os
# import re
import shutil
import pwd
import grp
import json

from ansible_collections.bodsch.core.plugins.module_utils.checksum import Checksum
from ansible_collections.bodsch.core.plugins.module_utils.diff import SideBySide
from ansible_collections.bodsch.core.plugins.module_utils.validate import validate
from ansible_collections.bodsch.cloud.plugins.module_utils.nextcloud.occ import Occ


class NextcloudConfig(Occ):
    """
    """
    module = None

    def __init__(self, module, owner, working_dir, cache_directory):
        """
        """
        super().__init__(module, owner, working_dir)  # Ruft den Konstruktor der Basisklasse Occ auf

        self.module = module

        # self.module.log(f"NextcloudConfig::__init__({owner}, {working_dir}, {cache_directory})")

        self.owner = owner
        self.working_dir = working_dir

        self.nc_config_file = f"{self.working_dir}/config/config.php"
        self.ansible_json_file = f"{self.working_dir}/config/ansible.json"

        self.cache_directory = cache_directory

        pid = os.getpid()
        self.tmp_directory = os.path.join("/run/.ansible", f"nextcloud.{str(pid)}")

    def import_file(self, config_file):
        """
        """
        # self.module.log(f"NextcloudConfig::import_file({config_file})")

        args = []
        args += self.occ_base_args

        args.append("config:import")
        args.append(config_file)
        args.append("--no-ansi")

        # self.module.log(msg=f" args: '{args}'")

        rc, out, err = self._exec(args, check_rc=False)

        return rc, out, err

    def config_list(self):
        """
        """
        self.module.log("NextcloudConfig::config_list()")
        pass

    def check_config(self, params):
        """
        """
        # self.module.log(f"NextcloudConfig::check_config({params})")

        self.owner = params.get("owner")
        self.group = params.get("group")
        self.config_parameters = params.get("config_parameters")
        self.trusted_domains = params.get("trusted_domains")
        self.database = params.get("database")
        self.diff_output = params.get("diff_output")

        checksum = Checksum(self.module)
        _diff = []

        os.chdir(self.working_dir)

        data = self.config_opts()

        # self.module.log(msg=f" config opts   : '{data}'")

        # create_directory(directory=self.tmp_directory, mode="0750")

        tmp_file = os.path.join(self.tmp_directory, "ansible.json")

        self.__write_config(tmp_file, data)

        new_checksum = checksum.checksum_from_file(tmp_file)
        old_checksum = checksum.checksum_from_file(self.ansible_json_file)
        changed = not (new_checksum == old_checksum)
        new_file = False
        msg = "The configuration has not been changed."

        # self.module.log(f" tmp_file      : {tmp_file}")
        # self.module.log(f" config_file   : {self.ansible_json_file}")
        # self.module.log(f" changed       : {changed}")
        # self.module.log(f" new_checksum  : {new_checksum}")
        # self.module.log(f" old_checksum  : {old_checksum}")

        # if self.data_dir:
        #     current_owner, current_group, current_mode = self.__file_state(self.data_dir)
        #     self.module.log(f" {self.data_dir} : {current_owner}:{current_mode} : {current_mode}")

        if changed:
            new_file = (old_checksum is None)
            _config_backup = os.path.join(self.working_dir, 'config', f"config.{os.getpid()}.bck")

            if self.diff_output:
                difference = self.create_diff(self.ansible_json_file, data)
                _diff = difference

            # create backup of existing config
            if os.path.exists(self.ansible_json_file):
                shutil.copyfile(self.nc_config_file, _config_backup)

            shutil.copyfile(tmp_file, self.ansible_json_file)

            """
                import new config
            """
            rc, out, err = self.import_file(self.ansible_json_file)

            """
                test new config
            """
            rc, _, _, _, err = self.status()

            if rc != 0:
                """
                    restore last running configuration
                """
                if os.path.exists(_config_backup):
                    os.remove(self.nc_config_file)
                    shutil.copyfile(_config_backup, self.nc_config_file)

                    if os.path.exists(_config_backup):
                        os.remove(_config_backup)

                msg = "The configuration holds an fatal error."
                msg += f" {err}"

                return dict(
                    failed=True,
                    msg=msg,
                    diff=_diff
                )

            else:
                msg = "The configuration has been successfully updated."

                if os.path.exists(_config_backup):
                    # self.module.log(f" remove config backup {_config_backup}")
                    os.remove(_config_backup)

        if new_file:
            msg = "The configuration was successfully created."

        uid, gid = self.module.user_and_group(self.nc_config_file)

        # self.module.log(f" uid {uid} / gid {gid}")

        self.__fix_ownership(self.nc_config_file, self.owner, self.group, "0666")

        shutil.rmtree(self.tmp_directory)

        return dict(
            changed=changed,
            failed=False,
            msg=msg,
            diff=_diff
        )

    def config_opts(self):
        """
        """
        data = dict(
            system=dict()
        )

        if validate(self.trusted_domains):
            data["system"]['trusted_domains'] = self.trusted_domains

        if self.config_parameters:
            parameters = self.config_parameters

            # self.module.log(f" parameters       : {parameters}")

            language = parameters.get("language")

            if language:
                if language.get("default", None):
                    data["system"]['default_language'] = language.get("default", None)

                if language.get("force", None):
                    data["system"]['force_language'] = language.get("force", None)

            locale = parameters.get("locale")

            if locale:
                if locale.get("default", None):
                    data["system"]['default_locale'] = locale.get("default", None)

                if locale.get("force", None):
                    data["system"]['force_locale'] = locale.get("force", None)

            if parameters.get("phone_region", None):
                data["system"]['default_phone_region'] = parameters.get("phone_region", None)

            if parameters.get("defaultapps", None):
                data["system"]['defaultapp'] = ",".join(parameters.get("defaultapps", []))

            if parameters.get("knowledgebase_enabled", None):
                data["system"]['knowledgebaseenabled'] = parameters.get("knowledgebase_enabled", None)

            if parameters.get("allow_user_to_change_display_name", None):
                data["system"]['allow_user_to_change_display_name'] = parameters.get("allow_user_to_change_display_name", None)

            if parameters.get("remember_login_cookie_lifetime", None):
                data["system"]['remember_login_cookie_lifetime'] = parameters.get("remember_login_cookie_lifetime", None)

            if parameters.get("theme", None):
                data["system"]["theme"] = parameters.get("theme")
            if parameters.get("enforce_theme", None):
                data["system"]["enforce_theme"] = parameters.get("enforce_theme")

            session = parameters.get("session")

            if session:
                if session.get("lifetime", None):
                    data["system"]['session_lifetime'] = session.get("lifetime", None)

                if session.get("relaxed_expiry", None):
                    data["system"]['session_relaxed_expiry'] = session.get("relaxed_expiry", None)

                if session.get("keepalive", None):
                    data["system"]['session_keepalive'] = session.get("keepalive", None)

            maintenance = parameters.get("maintenance")

            if maintenance:
                maintenance_enabled = maintenance.get("enabled", True)
                maintenance_window_start = maintenance.get("window_start", 1)
                if maintenance_enabled and maintenance_window_start:
                    data["system"]['maintenance_window_start'] = maintenance_window_start

            if parameters.get("auto_logout", None):
                data["system"]['auto_logout'] = parameters.get("auto_logout", None)

            token = parameters.get("token")

            if token:
                if token.get("auth_enforced", None):
                    data["system"]['token_auth_enforced'] = token.get("auth_enforced", None)

                if token.get("auth_activity_update", None):
                    data["system"]['token_auth_activity_update'] = token.get("auth_activity_update", None)

            auth = parameters.get("auth")

            if auth:
                if auth.get("bruteforce", {}).get("protection", {}).get("enabled", None):
                    data["system"]['auth.bruteforce.protection.enabled'] = auth.get("bruteforce", {}).get("protection", {}).get("enabled", None)

                if auth.get("bruteforce", {}).get("protection", {}).get("testing", None):
                    data["system"]['auth.bruteforce.protection.testing'] = auth.get("bruteforce", {}).get("protection", {}).get("testing", None)

                if auth.get("webauthn", {}).get("enabled", None):
                    data["system"]['auth.webauthn.enabled'] = auth.get("webauthn", {}).get("enabled", None)

                if auth.get("storeCryptedPassword", None):
                    data["system"]['auth.storeCryptedPassword'] = auth.get("storeCryptedPassword", None)

            if parameters.get("hide_login_form", None):
                data["system"]['hide_login_form'] = parameters.get("hide_login_form", None)

            if parameters.get("skeleton_directory", None):
                data["system"]['skeletondirectory'] = parameters.get("skeleton_directory", None)

            if parameters.get("template_directory", None):
                data["system"]['templatedirectory'] = parameters.get("template_directory", None)

            if parameters.get("temp_directory", None):
                data["system"]['tempdirectory'] = parameters.get("temp_directory", None)

            if parameters.get("update_directory", None):
                data["system"]['updatedirectory'] = parameters.get("update_directory", None)

            if parameters.get("data_directory", None):
                data["system"]['datadirectory'] = parameters.get("data_directory", None)

            if parameters.get("lost_password_link", None):
                data["system"]['lost_password_link'] = parameters.get("lost_password_link", None)

            if parameters.get("logo_url", None):
                data["system"]['logo_url'] = parameters.get("logo_url", None)

            mail = parameters.get("mail")

            if mail:
                if mail.get("domain", None):
                    data["system"]['mail_domain'] = mail.get("domain", None)

                if mail.get("from_address", None):
                    data["system"]['mail_from_address'] = mail.get("from_address", None)

                if mail.get("debug", None):
                    data["system"]['mail_smtpdebug'] = mail.get("debug", None)

                if mail.get("mode", None):
                    data["system"]['mail_smtpmode'] = mail.get("mode", None)

                if mail.get("hostname", None):
                    data["system"]['mail_smtphost'] = mail.get("hostname", None)

                if mail.get("port", None):
                    data["system"]['mail_smtpport'] = mail.get("port", None)

                if mail.get("timeout", None):
                    data["system"]['mail_smtptimeout'] = mail.get("timeout", None)

                if mail.get("secure", None):
                    data["system"]['mail_smtpsecure'] = mail.get("secure", None)

                mail_auth = mail.get("auth")

                if mail_auth:
                    mail_auth_enabled = mail_auth.get("enabled", False)

                    if mail_auth_enabled:
                        if mail_auth.get("enabled", False):
                            data["system"]['mail_smtpauth'] = mail_auth_enabled

                        if mail_auth.get("username", None):
                            data["system"]['mail_smtpname'] = mail_auth.get("username", None)

                        if mail_auth.get("password", None):
                            data["system"]['mail_smtppassword'] = mail_auth.get("password", None)

                        # if mail_auth.get("type", None):
                        #    data["system"]['mail_smtpauthtype'] = mail_auth.get("type", None)

                if mail.get("template_class", None):
                    template_class = mail.get("template_class", '\\OC\\Mail\\EMailTemplate')
                    t2 = template_class.replace('\\\\', '\\')
                    # self.module.log(f" template_class       : {template_class}")
                    # template_class = template_class.encode().decode('unicode_escape')
                    # self.module.log(f" template_class       : {template_class.encode().decode('unicode_escape')}")
                    # self.module.log(f" template_class       : {t2}")

                    data["system"]['mail_template_class'] = t2

                if mail.get("send_plaintext_only", None):
                    data["system"]['mail_send_plaintext_only'] = mail.get("send_plaintext_only", None)

                if mail.get("stream_options", None):
                    data["system"]['mail_smtpstreamoptions'] = mail.get("stream_options", None)

                if mail.get("sendmailmode", None):
                    data["system"]['mail_sendmailmode'] = mail.get("sendmailmode", None)

            proxy = parameters.get("proxy")

            if proxy:
                proxy_overwrite = proxy.get("overwrite")

                if proxy_overwrite:
                    if proxy_overwrite.get("hostname", None):
                        data["system"]['overwritehost'] = proxy_overwrite.get("hostname", None)

                    if proxy_overwrite.get("protocol", None):
                        data["system"]['overwriteprotocol'] = proxy_overwrite.get("protocol", None)

                    if proxy_overwrite.get("web_root", None):
                        data["system"]['overwritewebroot'] = proxy_overwrite.get("web_root", None)

                    if proxy_overwrite.get("cond_addr", None):
                        data["system"]['overwritecondaddr'] = proxy_overwrite.get("cond_addr", None)

                    if proxy_overwrite.get("cli_url", None):
                        data["system"]['overwrite.cli.url'] = proxy_overwrite.get("cli_url", None)

                proxy_htaccess = proxy.get("htaccess")

                if proxy_htaccess:
                    if proxy_htaccess.get("rewrite_base", None):
                        data["system"]['htaccess.RewriteBase'] = proxy_htaccess.get("rewrite_base", None)

                    if proxy_htaccess.get("ignore_front_controller", None):
                        data["system"]['htaccess.IgnoreFrontController'] = proxy_htaccess.get("ignore_front_controller", None)

                if proxy.get("proxy_name", None):
                    data["system"]['proxy'] = proxy.get("proxy_name", None)

                if proxy.get("password", None):
                    data["system"]['proxyuserpwd'] = proxy.get("password", None)

                if proxy.get("exclude", None):
                    data["system"]['proxyexclude'] = proxy.get("exclude", None)

                if proxy.get("allow_local_remote_servers", None):
                    data["system"]['allow_local_remote_servers'] = proxy.get("allow_local_remote_servers", None)

            trashbin = parameters.get("trashbin")

            if trashbin:
                if trashbin.get("retention_obligation", None):
                    data["system"]['trashbin_retention_obligation'] = trashbin.get("retention_obligation", None)

            versions = parameters.get("versions")

            if versions:
                if versions.get("retention_obligation", None):
                    data["system"]['versions_retention_obligation'] = versions.get("retention_obligation", None)

            if parameters.get("app_code_checker", None):
                data["system"]['appcodechecker'] = parameters.get("app_code_checker", None)

            update = parameters.get("update")

            if update:
                if update.get("checker", None):
                    data["system"]['updatechecker'] = update.get("checker", None)

                if update.get("server_url", None):
                    data["system"]['updater.server.url'] = update.get("server_url", None)

                if update.get("release_channel", None):
                    data["system"]['updater.release.channel'] = update.get("release_channel", None)

            if parameters.get("has_internet_connection", None):
                data["system"]['has_internet_connection'] = parameters.get("has_internet_connection", None)

            checks = parameters.get("checks")

            if checks:
                if checks.get("connectivity_domains", None):
                    data["system"]['connectivity_check_domains'] = checks.get("connectivity_domains", None)

                if checks.get("working_wellknown_setup", None):
                    data["system"]['check_for_working_wellknown_setup'] = checks.get("working_wellknown_setup", None)

                if checks.get("working_htaccess", None):
                    data["system"]['check_for_working_htaccess'] = checks.get("working_htaccess", None)

                if checks.get("data_directory_permissions", None):
                    data["system"]['check_data_directory_permissions'] = checks.get("data_directory_permissions", None)

            if parameters.get("config_is_read_only", None):
                data["system"]['config_is_read_only'] = parameters.get("config_is_read_only", None)

            logging = parameters.get("logging")

            if logging:
                if logging.get("type", None):
                    data["system"]['log_type'] = logging.get("type", None)

                if logging.get("type_audit", None):
                    data["system"]['log_type_audit'] = logging.get("type_audit", None)

                if logging.get("file", None):
                    data["system"]['logfile'] = logging.get("file", None)

                if logging.get("logfile_audit", None):
                    data["system"]['logfile_audit'] = logging.get("logfile_audit", None)

                if logging.get("filemode", None):
                    data["system"]['logfilemode'] = logging.get("filemode", None)

                if logging.get("level", None):
                    data["system"]['loglevel'] = logging.get("level", None)

                if logging.get("level_frontend", None):
                    data["system"]['loglevel_frontend'] = logging.get("level_frontend", None)

                if logging.get("syslog_tag", None):
                    data["system"]['syslog_tag'] = logging.get("syslog_tag", None)

                if logging.get("syslog_tag_audit", None):
                    data["system"]['syslog_tag_audit'] = logging.get("syslog_tag_audit", None)

                condition = logging.get("condition", {})

                if condition:
                    dictList = {}
                    for key, value in condition.items():
                        dictList[key] = value
                    data["system"]['log.condition'] = dictList

                if logging.get("dateformat", None):
                    data["system"]['logdateformat'] = logging.get("dateformat", None)

                if logging.get("timezone", None):
                    data["system"]['logtimezone'] = logging.get("timezone", None)

                if logging.get("query", None):
                    data["system"]['log_query'] = logging.get("query", None)

                if logging.get("rotate_size", None):
                    data["system"]['log_rotate_size'] = logging.get("rotate_size", None)

            if parameters.get("profiler", None):
                data["system"]['profiler'] = parameters.get("profiler", None)

            customclient = parameters.get("customclient")

            if customclient:
                if customclient.get("desktop", None):
                    data["system"]['customclient_desktop'] = customclient.get("desktop", None)

                if customclient.get("android", None):
                    data["system"]['customclient_android'] = customclient.get("android", None)

                if customclient.get("ios", None):
                    data["system"]['customclient_ios'] = customclient.get("ios", None)

                if customclient.get("ios_appid", None):
                    data["system"]['customclient_ios_appid'] = customclient.get("ios_appid", None)

            apps = parameters.get("apps")

            # self.module.log(f" apps       : {apps}")

            if apps:
                if apps.get("store", {}).get("enabled", None):
                    data["system"]['appstoreenabled'] = apps.get("store", {}).get("enabled", None)

                if apps.get("store", {}).get("url", None):
                    data["system"]['appstoreurl'] = apps.get("store", {}).get("url", None)

                if apps.get("allowlist", None):
                    data["system"]['appsallowlist'] = apps.get("allowlist", None)

                if apps.get("paths", None):
                    data["system"]['apps_paths'] = apps.get("paths", None)

            image_previews = parameters.get("image_previews")

            if image_previews:
                if image_previews.get("enabled", None):
                    data["system"]['enable_previews'] = image_previews.get("enabled", None)

                if image_previews.get("concurrency", {}).get("all", None):
                    data["system"]['preview_concurrency_all'] = image_previews.get("concurrency", {}).get("all", None)

                if image_previews.get("concurrency", {}).get("new", None):
                    data["system"]['preview_concurrency_new'] = image_previews.get("concurrency", {}).get("new", None)

                if image_previews.get("max_x", None):
                    data["system"]['preview_max_x'] = image_previews.get("max_x", None)

                if image_previews.get("max_y", None):
                    data["system"]['preview_max_y'] = image_previews.get("max_y", None)

                if image_previews.get("max_filesize_image", None):
                    data["system"]['preview_max_filesize_image'] = image_previews.get("max_filesize_image", None)

                if image_previews.get("max_memory", None):
                    data["system"]['preview_max_filesize_image'] = image_previews.get("max_memory", None)

                if image_previews.get("preview_max_memory", None):
                    data["system"]['preview_max_filesize_image'] = image_previews.get("preview_max_memory", None)

                if image_previews.get("libreoffice_path", None):
                    data["system"]['preview_libreoffice_path'] = image_previews.get("libreoffice_path", None)

                if image_previews.get("office_cl_parameters", None):
                    data["system"]['preview_office_cl_parameters'] = " ".join(image_previews.get("office_cl_parameters", None))

                if image_previews.get("ffmpeg_path", None):
                    data["system"]['preview_ffmpeg_path'] = image_previews.get("ffmpeg_path", None)

                if image_previews.get("preview_imaginary_url", None):
                    data["system"]['preview_libreoffice_path'] = image_previews.get("imaginary_url", None)

            memcache = parameters.get("memcache")

            if memcache:
                if memcache.get("local", None):
                    data["system"]['memcache.local'] = memcache.get("local", None)

                if memcache.get("distributed", None):
                    data["system"]['memcache.distributed'] = memcache.get("distributed", None)

                if memcache.get("locking", None):
                    data["system"]['memcache.locking'] = memcache.get("locking", None)

                memcache_servers = memcache.get("servers", [])

                if memcache_servers:
                    memchache_array = [list(x.values()) for x in memcache_servers]
                    data["system"]['memcached_servers'] = memchache_array

                if memcache.get("options", None):
                    data["system"]['memcached_options'] = memcache.get("options", None)

            redis = parameters.get("redis")

            # TODO
            # no array .. only single entry
            if redis:
                redis_array = []
                for r in redis:
                    a = {}
                    if r.get("host", None):
                        a["host"] = r.get("host", None)
                    if r.get("port", None):
                        a["port"] = r.get("port", None)
                    if r.get("timeout", None):
                        a["timeout"] = r.get("timeout", None)
                    if r.get("password", None):
                        a["password"] = r.get("password", None)
                    if r.get("dbindex", None):
                        a["dbindex"] = r.get("dbindex", None)

                    redis_array.append(a)
                data["system"]["redis"] = redis_array

        if self.database:
            parameters = self.database

            if parameters.get("type", None) == "mysql":
                if parameters.get("mysql", {}).get("utf8mb4", None):
                    data["system"]['mysql.utf8mb4'] = parameters.get("mysql", {}).get("utf8mb4", None)

                if parameters.get("mysql", {}).get("collation", None):
                    data["system"]['mysql.collation'] = parameters.get("mysql", {}).get("collation", None)

                if parameters.get("username", None):
                    data["system"]['dbuser'] = parameters.get("username", None)

                if parameters.get("password", None):
                    data["system"]['dbpassword'] = parameters.get("password", None)

                if parameters.get("hostname", None):
                    data["system"]['dbhost'] = parameters.get("hostname", None)

                if parameters.get("port", None):
                    data["system"]['dbport'] = parameters.get("port", None)

                if parameters.get("schema", None):
                    data["system"]['dbname'] = parameters.get("schema", None)

                if parameters.get("tableprefix", None):
                    data["system"]['dbtableprefix'] = parameters.get("tableprefix", None)

            if parameters.get("type", None) == "sqlite3":
                if parameters.get("sqlite", {}).get("journal_mode", None):
                    data["system"]['sqlite.journal_mode'] = parameters.get("sqlite", {}).get("journal_mode", None)

        """

        """

        return data

    def create_diff(self, config_file, data):
        """
        """
        old_data = dict()

        if os.path.isfile(config_file):
            with open(config_file) as json_file:
                old_data = json.load(json_file)

        side_by_side = SideBySide(self.module, old_data, data)
        diff_side_by_side = side_by_side.diff(width=140, left_title="  Original", right_title="  Update")

        return diff_side_by_side

    def __values_as_string(self, values):
        """
        """
        result = {}
        # self.module.log(msg=f"{json.dumps(values, indent=2, sort_keys=False)}")

        if isinstance(values, dict):
            for k, v in sorted(values.items()):
                if isinstance(v, bool):
                    v = str(v).lower()
                result[k] = str(v)

        # self.module.log(msg=f"{json.dumps(result, indent=2, sort_keys=False)}")

        return result

    def __write_config(self, file_name, data):
        """
        """
        with open(file_name, 'w') as fp:
            json_data = json.dumps(data, indent=2, sort_keys=False)
            fp.write(f'{json_data}\n')

    def __file_state(self, file_name):
        """
        """
        current_owner = None
        current_group = None
        current_mode = None

        if os.path.exists(file_name):
            _state = os.stat(file_name)
            try:
                current_owner = pwd.getpwuid(_state.st_uid).pw_uid
            except KeyError:
                pass

            try:
                current_group = grp.getgrgid(_state.st_gid).gr_gid
            except KeyError:
                pass

            try:
                current_mode = oct(_state.st_mode)[-4:]
            except KeyError:
                pass

        return current_owner, current_group, current_mode

    def __fix_ownership(self, file_name, force_owner=None, force_group=None, force_mode=False):
        """
        """
        changed = False
        error_msg = None

        if os.path.exists(file_name):
            current_owner, current_group, current_mode = self.__file_state(file_name)

            # change mode
            if force_mode is not None and force_mode != current_mode:
                try:
                    if isinstance(force_mode, int):
                        mode = int(str(force_mode), base=8)
                except Exception as e:
                    error_msg = f" - ERROR '{e}'"
                    print(error_msg)

                try:
                    if isinstance(force_mode, str):
                        mode = int(force_mode, base=8)
                except Exception as e:
                    error_msg = f" - ERROR '{e}'"
                    print(error_msg)

                os.chmod(file_name, mode)

            # change ownership
            if force_owner is not None or force_group is not None and (force_owner != current_owner or force_group != current_group):
                if force_owner is not None:
                    try:
                        force_owner = pwd.getpwnam(str(force_owner)).pw_uid
                    except KeyError:
                        force_owner = int(force_owner)
                        pass
                elif current_owner is not None:
                    force_owner = current_owner
                else:
                    force_owner = 0

                if force_group is not None:
                    try:
                        force_group = grp.getgrnam(str(force_group)).gr_gid
                    except KeyError:
                        force_group = int(force_group)
                        pass
                elif current_group is not None:
                    force_group = current_group
                else:
                    force_group = 0

                os.chown(
                    file_name,
                    int(force_owner),
                    int(force_group)
                )

            _owner, _group, _mode = self.__file_state(file_name)

            if (current_owner != _owner) or (current_group != _group) or (current_mode != _mode):
                changed = True

        return changed, error_msg
