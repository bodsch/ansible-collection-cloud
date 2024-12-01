 
# Ansible Role:  `collabora`

Ansible role to install and configure [collabora office](https://www.collaboraoffice.com).

---

> I am in the process of transferring this role to a [collection](https://github.com/bodsch/ansible-collection-cloud) and will therefore no longer process any issues or merge requests here.  
> However, I will include them in the collection!  
> **Please be patient until I have completed the work!**

---

[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collabora/main.yml?logo=github&branch=main)][ci]
[![GitHub issues](https://img.shields.io/github/issues/bodsch/ansible-collabora?logo=github)][issues]
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/bodsch/ansible-collabora?logo=github)][releases]
[![Ansible Downloads](https://img.shields.io/ansible/role/d/bodsch/collabora?logo=ansible)][galaxy]

[ci]: https://github.com/bodsch/ansible-collabora/actions
[issues]: https://github.com/bodsch/ansible-collabora/issues?q=is%3Aopen+is%3Aissue
[releases]: https://github.com/bodsch/ansible-collabora/releases
[galaxy]: https://galaxy.ansible.com/ui/standalone/roles/bodsch/collabora/


## Requirements & Dependencies

Ansible Collections

- [bodsch.core](https://github.com/bodsch/ansible-collection-core)

```bash
ansible-galaxy collection install bodsch.core
```
or
```bash
ansible-galaxy collection install --requirements-file collections.yml
```

## usage

```yaml
collabora_user_default: cool

collabora_service: {}

collabora_config: {}
```

### `collabora_service`

```yaml
collabora_service:
  pidfile: ""
  port: ""
  disable_ssl: true
  disable_cool_user_checking: true
  # defaults:
  # sys_template_path=/opt/cool/systemplate
  # child_root_path=/opt/cool/child-roots
  # file_server_root_path=/usr/share/coolwsd
  overrides:
    sys_template_path: /opt/cool/systemplate
    child_root_path: /opt/cool/child-roots
    file_server_root_path: /usr/share/coolwsd
  config_file: ""
  config_dir: ""
  lo_template_path: ""
```

### `collabora_config`

```yaml
collabora_config:
  # The languages allowed.
  allowed_languages: []
  fetch_update_check: 24                      # hours
  cache_path: /var/cache/loolwsd
  # You can manage the mounting feature. Either "false" or "true". (As a string.)
  mount_jail_tree: true
  server_name: ""
  logging: {}
  #
  trace_event:
    enable: false
    path: /var/log/coolwsd.trace.json
  #
  network: {}
  #
  ssl: {}
  #
  security:
    seccomp: ""
    capabilities: ""
    jwt_expiry_secs: ""
    enable_macros_execution: ""
    macro_security_level: ""
    enable_websocket_urp: ""
    enable_metrics_unauthenticated: ""
  #
  watermark:
    opacity: ""
    text: ""
  #
  user_interface:
    # Controls the user interface style.
    # The 'default' means: Take the value from ui_defaults, or decide for one of compact or tabbed (default|compact|tabbed)
    mode: ""
    # Use theme from the integrator
    use_integration_theme: true
  #
  storage: {}
  #
  admin_console: {}
```

### `collabora_config.logging`

```yaml
collabora_config:

  logging:
    color: true
    # Set the log level. Can be 0 through 8, none or "fatal", "critical", "error",
    # "warning", "notice", "information", "debug", "trace".
    level: warning
    startup: information
    most_verbose: notice
    least_verbose: fatal
    file:
      enable: false
      path: /var/log/loolwsd.log
      rotation: never
      archive: timestamp
      compress: true
      purge:
        days: 10
        count: 10
      rotate_on_open: true
      flush: false

    anonymize:
      user_data: true
      salt: ""
    docstats: false
    userstats: false
```

### `collabora_config.storage`

```yaml
collabora_config:

  storage:
    hosts: []
      #   - description: ""
      #     allow: ""
      #     host: ""
    wopi:
      allow: true
      # Maximum document size in bytes to load. 0 for unlimited.
      max_file_size: 0
      locking:
        refresh: 900
      alias_groups:
        # default mode is 'first' /  set mode to 'groups' and define group to allow multiple host
        mode: "first"          
        groups: []
      #   - description: ""
      #     allow: ""
      #     host: ""
      #     aliases: []
```

### `collabora_config.network`

```yaml
collabora_config:

  network:
    # Protocol to use IPv4, IPv6 or all for both
    proto: IPv4
    # Listen address that coolwsd binds to. Can be 'any' or 'loopback'.
    listen: loopback
    # Allow/deny client IP address for POST(REST).
    post_allow:
      hosts: []
        # - description: "The IPv4 private 10.0.0.0/8 subnet (Podman)."
        #   network: '10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}'
        # - description: "Ditto, but as IPv4-mapped IPv6 addresses"
        #   network: '::ffff:10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}'

    # Allowed hosts as an external data source inside edited files.
    # All allowed post_allow.host and storage.wopi entries are also considered to be
    # allowed as a data source.
    # Used for example in: PostMessage Action_InsertGraphics, =WEBSERVICE() function, external reference in the cell.
    lok_allow:
      hosts: []
        # - description: "Localhost access by name"
        #   network: 'localhost
```


### `collabora_config.ssl`

```yaml
collabora_config:

  ssl:
    # Controls whether SSL encryption between coolwsd and the network is enabled (do not disable for production deployment). If default is false, must first be compiled with SSL support to enable.
    enabled: false
    # Connection via proxy where coolwsd acts as working via https, but actually uses http.
    termination: false
    # These settings become relevant when `collabora_ssl_enabled` is set to
    # `yes`.
    cert_file: /etc/coolwsd/cert.pem
    key_file: /etc/coolwsd/key.pem
    ca_file: /etc/coolwsd/ca-chain.cert.pem
    cipher_list:
      - "ALL"
      - "!ADH"
      - "!LOW"
      - "!EXP"
      - "!MD5"
      - "@STRENGTH"
    # Enable HTTP Public key pinning
    hpkp:
      enable: false
      report_only: false
      # HPKP's max-age directive - time in seconds browser should remember the pins
      max_age: 1000
      # HPKP's report-uri directive - pin validation failure are reported at this URL
      report_enable: false
      report_uri:
      # Base64 encoded SPKI fingerprints of keys to be pinned
      pins: []
    # Strict-Transport-Security settings, per rfc6797. Subdomains are always included.
    sts:
      # Whether or not Strict-Transport-Security is enabled. Enable only when ready for production. Cannot be disabled without resetting the browsers.
      enabled: false
      # Strict-Transport-Security max-age directive, in seconds. 0 is allowed; please see rfc6797 for details. Defaults to 1 year.
      max_age: 31536000
```

### `collabora_config.admin_console`

```yaml
collabora_config:

  admin_console:
    enable: true
    # Enable admin user authentication with PAM
    enable_pam: false
    # The username of the admin console. Ignored if PAM is enabled.
    username: "admin"
    # The password of the admin console. Deprecated on most platforms. Instead, use PAM or coolconfig to set up a secure password.
    password: "50m3-53cu23-p455w02d."
    # Log admin activities irrespective of logging.level
    logging:
      # log when an admin logged into the console
      admin_login: true
      # log when metrics endpoint is accessed and metrics endpoint authentication is enabled
      metrics_fetch: true
      # log when external monitor gets connected
      monitor_connect: true
      # log when admin does some action for example killing a process
      admin_action: true
```
---

## Admin Console

[collabora.molecule.lan](https://collabora.molecule.lan/browser/dist/admin/admin.html)

---

## Contribution

Please read [Contribution](CONTRIBUTING.md)

## Development,  Branches (Git Tags)

The `master` Branch is my *Working Horse* includes the "latest, hot shit" and can be complete broken!

If you want to use something stable, please use a [Tagged Version](https://github.com/bodsch/ansible-collabora/-/tags)!

---

## Author and License

- Bodo Schulz

## License

[Apache](LICENSE)

**FREE SOFTWARE, HELL YEAH!**
