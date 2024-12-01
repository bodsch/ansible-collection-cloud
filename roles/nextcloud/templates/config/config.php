<?php
/* ------------------------------------------------------------------------------------------------------------ */

/* ------------------------------------------------------------------------------------------------------------ */

/**
 * Override where Nextcloud stores temporary files. Useful in situations where
 * the system temporary directory is on a limited space ramdisk or is otherwise
 * restricted, or if external storage which do not support streaming are in
 * use.
 *
 * The Web server user/PHP must have write access to this directory.
 * Additionally you have to make sure that your PHP configuration considers this a valid
 * tmp directory, by setting the TMP, TMPDIR, and TEMP variables to the required directories.
 * On top of that you might be required to grant additional permissions in AppArmor or SELinux.
 */
'tempdirectory' => '/tmp/nextcloudtemp',

/**
 * Override where Nextcloud stores update files while updating. Useful in situations
 * where the default `datadirectory` is on network disk like NFS, or is otherwise
 * restricted. Defaults to the value of `datadirectory` if unset.
 *
 * The Web server user must have write access to this directory.
 */
'updatedirectory' => '',

/**
 * Blacklist a specific file or files and disallow the upload of files
 * with this name. ``.htaccess`` is blocked by default.
 * WARNING: USE THIS ONLY IF YOU KNOW WHAT YOU ARE DOING.
 *
 * Defaults to ``array('.htaccess')``
 */
'blacklisted_files' => ['.htaccess'],

/**
 * If you are applying a theme to Nextcloud, enter the name of the theme here.
 * The default location for themes is ``nextcloud/themes/``.
 *
 * Defaults to the theming app which is shipped since Nextcloud 9
 */
'theme' => '',

/**
 * Enforce the user theme. This will disable the user theming settings
 * This must be a valid ITheme ID.
 * E.g. light, dark, highcontrast, dark-highcontrast...
 */
'enforce_theme' => '',

/**
 * The default cipher for encrypting files. Currently supported are:
 *  - AES-256-CTR
 *  - AES-128-CTR
 *  - AES-256-CFB
 *  - AES-128-CFB
 *
 * Defaults to ``AES-256-CTR``
 */
'cipher' => 'AES-256-CTR',

/**
 * Use the legacy base64 format for encrypted files instead of the more space-efficient
 * binary format. The option affects only newly written files, existing encrypted files
 * will not be touched and will remain readable whether they use the new format or not.
 *
 * Defaults to ``false``
 */
'encryption.use_legacy_base64_encoding' => false,

/**
 * The minimum Nextcloud desktop client version that will be allowed to sync with
 * this server instance. All connections made from earlier clients will be denied
 * by the server. Defaults to the minimum officially supported Nextcloud desktop
 * client version at the time of release of this server version.
 *
 * When changing this, note that older unsupported versions of the Nextcloud desktop
 * client may not function as expected, and could lead to permanent data loss for
 * clients or other unexpected results.
 *
 * Defaults to ``2.3.0``
 */
'minimum.supported.desktop.version' => '2.3.0',

/**
 * Option to allow local storage to contain symlinks.
 * WARNING: Not recommended. This would make it possible for Nextcloud to access
 * files outside the data directory and could be considered a security risk.
 *
 * Defaults to ``false``
 */
'localstorage.allowsymlinks' => false,

/**
 * Nextcloud overrides umask to ensure suitable access permissions
 * regardless of webserver/php-fpm configuration and worker state.
 * WARNING: Modifying this value has security implications and
 * may soft-break the installation.
 *
 * Most installs shall not modify this value.
 *
 * Defaults to ``0022``
 */
'localstorage.umask' => 0022,

/**
 * This options allows storage systems that don't allow to modify existing files
 * to overcome this limitation by removing the files before overwriting.
 *
 * Defaults to ``false``
 */
'localstorage.unlink_on_truncate' => false,

/**
 * EXPERIMENTAL: option whether to include external storage in quota
 * calculation, defaults to false.
 *
 * Defaults to ``false``
 */
'quota_include_external_storage' => false,

/**
 * When an external storage is unavailable for some reasons, it will be flagged
 * as such for 10 minutes. When the trigger is a failed authentication attempt
 * the delay is higher and can be controlled with this option. The motivation
 * is to make account lock outs at Active Directories (and compatible) more
 * unlikely.
 *
 * Defaults to ``1800`` (seconds)
 */
'external_storage.auth_availability_delay' => 1800,

/**
 * Allows to create external storages of type "Local" in the web interface and APIs.
 *
 * When disabled, it is still possible to create local storages with occ using
 * the following command:
 *
 * % php occ files_external:create /mountpoint local null::null -c datadir=/path/to/data
 *
 * Defaults to ``true``
 *
 */
'files_external_allow_create_new_local' => true,

/**
 * Specifies how often the local filesystem (the Nextcloud data/ directory, and
 * NFS mounts in data/) is checked for changes made outside Nextcloud. This
 * does not apply to external storage.
 *
 * 0 -> Never check the filesystem for outside changes, provides a performance
 * increase when it's certain that no changes are made directly to the
 * filesystem
 *
 * 1 -> Check each file or folder at most once per request, recommended for
 * general use if outside changes might happen.
 *
 * Defaults to ``0``
 */
'filesystem_check_changes' => 0,

/**
 * By default, Nextcloud will store the part files created during upload in the
 * same storage as the upload target. Setting this to false will store the part
 * files in the root of the users folder which might be required to work with certain
 * external storage setups that have limited rename capabilities.
 *
 * Defaults to ``true``
 */
'part_file_in_storage' => true,

/**
 * Where ``mount.json`` file should be stored, defaults to ``data/mount.json``
 * in the Nextcloud directory.
 *
 * Defaults to ``data/mount.json`` in the Nextcloud directory.
 */
'mount_file' => '/var/www/nextcloud/data/mount.json',

/**
 * When ``true``, prevent Nextcloud from changing the cache due to changes in
 * the filesystem for all storage.
 *
 * Defaults to ``false``
 */
'filesystem_cache_readonly' => false,

/**
 * Secret used by Nextcloud for various purposes, e.g. to encrypt data. If you
 * lose this string there will be data corruption.
 */
'secret' => '',

/**
 * List of trusted proxy servers
 *
 * You may set this to an array containing a combination of
 * - IPv4 addresses, e.g. `192.168.2.123`
 * - IPv4 ranges in CIDR notation, e.g. `192.168.2.0/24`
 * - IPv6 addresses, e.g. `fd9e:21a7:a92c:2323::1`
 * - IPv6 ranges in CIDR notation, e.g. `2001:db8:85a3:8d3:1319:8a20::/95`
 *
 * When an incoming request's `REMOTE_ADDR` matches any of the IP addresses
 * specified here, it is assumed to be a proxy instead of a client. Thus, the
 * client IP will be read from the HTTP header specified in
 * `forwarded_for_headers` instead of from `REMOTE_ADDR`.
 *
 * So if you configure `trusted_proxies`, also consider setting
 * `forwarded_for_headers` which otherwise defaults to `HTTP_X_FORWARDED_FOR`
 * (the `X-Forwarded-For` header).
 *
 * Defaults to an empty array.
 */
'trusted_proxies' => ['203.0.113.45', '198.51.100.128', '192.168.2.0/24'],

/**
 * Headers that should be trusted as client IP address in combination with
 * `trusted_proxies`. If the HTTP header looks like 'X-Forwarded-For', then use
 * 'HTTP_X_FORWARDED_FOR' here.
 *
 * If set incorrectly, a client can spoof their IP address as visible to
 * Nextcloud, bypassing access controls and making logs useless!
 *
 * Defaults to ``'HTTP_X_FORWARDED_FOR'``
 */
'forwarded_for_headers' => ['HTTP_X_FORWARDED', 'HTTP_FORWARDED_FOR'],

/**
 * max file size for animating gifs on public-sharing-site.
 * If the gif is bigger, it'll show a static preview
 *
 * Value represents the maximum filesize in megabytes. Set to ``-1`` for
 * no limit.
 *
 * Defaults to ``10`` megabytes
 */
'max_filesize_animated_gifs_public_sharing' => 10,


/**
 * Enables transactional file locking.
 * This is enabled by default.
 *
 * Prevents concurrent processes from accessing the same files
 * at the same time. Can help prevent side effects that would
 * be caused by concurrent operations. Mainly relevant for
 * very large installations with many users working with
 * shared files.
 *
 * Defaults to ``true``
 */
'filelocking.enabled' => true,

/**
 * Set the lock's time-to-live in seconds.
 *
 * Any lock older than this will be automatically cleaned up.
 *
 * Defaults to ``60*60`` seconds (1 hour) or the php
 *             max_execution_time, whichever is higher.
 */
'filelocking.ttl' => 60*60,

/**
 * Memory caching backend for file locking
 *
 * Because most memcache backends can clean values without warning using redis
 * is highly recommended to *avoid data loss*.
 *
 * Defaults to ``none``
 */
'memcache.locking' => '\\OC\\Memcache\\Redis',

/**
 * Enable locking debug logging
 *
 * Note that this can lead to a very large volume of log items being written which can lead
 * to performance degradation and large log files on busy instance.
 *
 * Thus enabling this in production for longer periods of time is not recommended
 * or should be used together with the ``log.condition`` setting.
 */
'filelocking.debug' => false,

/**
 * Disable the web based updater
 */
'upgrade.disable-web' => false,

/**
 * Allows to modify the cli-upgrade link in order to link to a different documentation
 */
'upgrade.cli-upgrade-link' => '',

/**
 * Set this Nextcloud instance to debugging mode
 *
 * Only enable this for local development and not in production environments
 * This will disable the minifier and outputs some additional debug information
 *
 * Defaults to ``false``
 */
'debug' => false,

/**
 * Sets the data-fingerprint of the current data served
 *
 * This is a property used by the clients to find out if a backup has been
 * restored on the server. Once a backup is restored run
 * ./occ maintenance:data-fingerprint
 * To set this to a new value.
 *
 * Updating/Deleting this value can make connected clients stall until
 * the user has resolved conflicts.
 *
 * Defaults to ``''`` (empty string)
 */
'data-fingerprint' => '',

/**
 * This entry is just here to show a warning in case somebody copied the sample
 * configuration. DO NOT ADD THIS SWITCH TO YOUR CONFIGURATION!
 *
 * If you, brave person, have read until here be aware that you should not
 * modify *ANY* settings in this file without reading the documentation.
 */
'copied_sample_config' => true,

/**
 * use a custom lookup server to publish user data
 */
'lookup_server' => 'https://lookup.nextcloud.com',

/**
 * set to true if the server is used in a setup based on Nextcloud's Global Scale architecture
 */
'gs.enabled' => false,

/**
 * by default federation is only used internally in a Global Scale setup
 * If you want to allow federation outside your environment set it to 'global'
 */
'gs.federation' => 'internal',

/**
 * List of incompatible user agents opted out from Same Site Cookie Protection.
 * Some user agents are notorious and don't really properly follow HTTP
 * specifications. For those, have an opt-out.
 *
 * WARNING: only use this if you know what you are doing
 */
'csrf.optout' => [
        '/^WebDAVFS/', // OS X Finder
        '/^Microsoft-WebDAV-MiniRedir/', // Windows webdav drive
],

/**
 * By default, there is on public pages a link shown that allows users to
 * learn about the "simple sign up" - see https://nextcloud.com/signup/
 *
 * If this is set to "false" it will not show the link.
 */
'simpleSignUpLink.shown' => true,

/**
 * By default, autocompletion is enabled for the login form on Nextcloud's login page.
 * While this is enabled, browsers are allowed to "remember" login names and such.
 * Some companies require it to be disabled to comply with their security policy.
 *
 * Simply set this property to "false", if you want to turn this feature off.
 */

'login_form_autocomplete' => true,

/**
 * If your user is using an outdated or unsupported browser, a warning will be shown
 * to offer some guidance to upgrade or switch and ensure a proper Nextcloud experience.
 * They can still bypass it after they have read the warning.
 *
 * Simply set this property to "true", if you want to turn this feature off.
 */

'no_unsupported_browser_warning' => false,

/**
 * Disable background scanning of files
 *
 * By default, a background job runs every 10 minutes and execute a background
 * scan to sync filesystem and database. Only users with unscanned files
 * (size < 0 in filecache) are included. Maximum 500 users per job.
 *
 * Defaults to ``false``
 */
'files_no_background_scan' => false,

/**
 * Log all queries into a file
 *
 * Warning: This heavily decreases the performance of the server and is only
 * meant to debug/profile the query interaction manually.
 * Also, it might log sensitive data into a plain text file.
 */
'query_log_file' => '',

/**
 * Log all redis requests into a file
 *
 * Warning: This heavily decreases the performance of the server and is only
 * meant to debug/profile the redis interaction manually.
 * Also, it might log sensitive data into a plain text file.
 */
'redis_log_file' => '',

/**
 * Log all LDAP requests into a file
 *
 * Warning: This heavily decreases the performance of the server and is only
 * meant to debug/profile the LDAP interaction manually.
 * Also, it might log sensitive data into a plain text file.
 */
'ldap_log_file' => '',

/**
 * Enable diagnostics event logging
 *
 * If enabled the timings of common execution steps will be logged to the
 * Nextcloud log at debug level. log.condition is useful to enable this on
 * production systems to only log under some conditions
 */
'diagnostics.logging' => true,

/**
 * Limit diagnostics event logging to events longer than the configured threshold in ms
 *
 * when set to 0 no diagnostics events will be logged
 */
'diagnostics.logging.threshold' => 0,

/**
 * Enable profile globally
 *
 * Defaults to ``true``
 */
'profile.enabled' => true,

/**
 * Enable file metadata collection
 *
 * This is helpful for the mobile clients and will enable few optimizations in
 * the future for the preview generation.
 *
 * Note that when enabled, this data will be stored in the database and might increase
 * the database storage.
 */
'enable_file_metadata' => true,

/**
 * Allows to override the default scopes for Account data.
 * The list of overridable properties and valid values for scopes are in
 * ``OCP\Accounts\IAccountManager``. Values added here are merged with
 * default values, which are in ``OC\Accounts\AccountManager``.
 *
 * For instance, if the phone property should default to the private scope
 * instead of the local one:
 *
 * ::
 *
 *      [
 *        \OCP\Accounts\IAccountManager::PROPERTY_PHONE => \OCP\Accounts\IAccountManager::SCOPE_PRIVATE
 *      ]
 *
 */
'account_manager.default_property_scope' => [],

/**
 * Enable the deprecated Projects feature,
 * superseded by Related resources as of Nextcloud 25
 *
 * Defaults to ``false``
 */
'projects.enabled' => false,

/**
 * Enable the bulk upload feature.
 *
 * Defaults to ``true``
 */
'bulkupload.enabled' => true,

/**
 * Enables fetching open graph metadata from remote urls
 *
 * Defaults to ``true``
 */
'reference_opengraph' => true,
#}
);

