 
# Ansible Role:  `bodsch.cloud.nextcloud`

Ansible role to install and configure nextcloud.


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
nextcloud_version: 26.0.5

# switch between
# releases      : https://download.nextcloud.com/server/releases/nextcloud-28.0.1.zip
# prereleases   : https://download.nextcloud.com/server/prereleases/nextcloud-28.0.2rc1.zip
# daily         : https://download.nextcloud.com/server/daily/nextcloud-28-daily-2024-01-18.zip
#                 https://download.nextcloud.com/server/daily/nextcloud-master-daily-2024-01-18.zip
# default = releases
nextcloud_release_type: releases

nextcloud_direct_download: false

nextcloud_release: {}

nextcloud_install_base_directory: /var/www

nextcloud_owner: ""
nextcloud_group: ""

nextcloud_admin:
  username: admin
  password: admin

nextcloud_password_validation:
  upper_and_lower_case: true
  special_character: false
  numeric_character: false
  length: 10
  
nextcloud_instande_id: ""
nextcloud_password_salt: ""
nextcloud_data_directory: ""

nextcloud_trusted_domains: []

nextcloud_database:
  type: sqlite
  name: nextcloud
  # username: nextcloud
  # password:
  # hostname:
  # port: 3306
  # schema: nextcloud
  persistent: false

nextcloud_defaults: {}
  # language:
  #   default: en
  #   # force: en
  # locale:
  #   default: en_GB
  #   # force: en_GB
  # phone_region: DE
  # defaultapps:
  #   - dashboard
  #   - files
  # knowledgebase_enabled: true

nextcloud_php_daemon:
  restart: true
  name: "{{ php_fpm_daemon }}"

nextcloud_background_jobs:
  type: cron          # alternative: webcron | ajax and systemd
  daemon: ""          # "{{ 'cron' if ansible_os_family | lower == 'debian' else 'cronie' }}"
  state: enabled      # ['enabled', 'disabled']
  cron:
    minute: ""        # '*/5'
    hour: ""          # '*'
    weekday: ""       # '*'
```

### `nextcloud_admin`

```yaml
nextcloud_admin:
  username: admin
  password: admin
```

### `nextcloud_trusted_domains`

```yaml
nextcloud_trusted_domains:
  - nextcloud.molecule.lan
  - nextcloud.molecule.local
```

### `nextcloud_database`

```yaml
nextcloud_database:
  type: sqlite
  name: nextcloud
  # username: nextcloud
  # password:
  # hostname:
  # port: 3306
  # schema: nextcloud
  persistent: false
```

### `nextcloud_defaults`

```yaml
nextcloud_defaults:
  # language:
  #   default: en
  #   # force: en
  # locale:
  #   default: en_GB
  #   # force: en_GB
  # phone_region: DE
  # defaultapps:
  #   - dashboard
  #   - files
  # knowledgebase_enabled: true
```

### `nextcloud_background_jobs`

To create the Background Job.

| Variable       | default    | Description |
| :---           | :----      | :----       |
| `type`         | `webcron`  | alternative: `cron`, `webcron`, `ajax`.<br>systemd User can create an system timer with `systemd` insteed `cron` |
| `daemon`       | ` `        | the named cron package (Will be installed) |
| `enabled`      | `false`    | enable cron Background Jobs.    |
| `cron.minute`  | `*/5`      | cron configuration: *minute*    |
| `cron.hour`    | `*`        | cron configuration: *hour*      |
| `cron.weekday` | `*`        | cron configuration: *weekday*   |

```yaml
nextcloud_background_jobs:
  type: cron
  daemon: ""
  enabled: false
  cron:
    minute: ""
    hour: ""
    weekday: ""
```

### `nextcloud_groups`

Creates Groups in Nextcloud.

| Variable       | default    | Description |
| :---           | :----      | :----       |
| `name`         | `webcron`  | Group name |
| `display_name` | ` `        | Group name used in the web UI (can contain any characters) |
| `state`        | `present`  | State of the Group (`present` or `absent`) |

```yaml
nextcloud_groups:
  - name: test
    display_name: "Testing with spaces"
    state: present
  - name: test2
    state: absent
```

### `nextcloud_users`

Creates Users in Nextcloud.

| Variable        | default    | Description |
| :---            | :----      | :----       |
| `name`          | ` `        | User name |
| `state`         | `present`  | State of the User (`present` or `absent`) |
| `display_name`  | ` `        | User name used in the web UI (can contain any characters) |
| `password`      | ` `        | User password |
| `resetpassword` | ` `        | reset the passsword (**every time the playbook is run!**) |
| `groups`        | `[]`       | A list of groups to which the user should be added.<br>Groups that do not exist are ignored. |
| `settings`      | ``         | *TODO* |


```yaml
nextcloud_users:
  - name: bodsch
    password: "{{ vault__users.bodsch }}"
    display_name: Bod Sch
    groups:
      - test
```

### `nextcloud_apps`

Install Nextcloud Apps.

| Variable        | default    | Description |
| :---            | :----      | :----       |
| `name`          | ` `        | App name |
| `state`         | `present`  | State of the App (`present`, `absent`, `enabled` or `disabled` ) |
| `settings`      | `{}`       | Dictionary of Application Settings |

```yaml
nextcloud_apps:
  - name: calendar
    state: disabled
  - name: richdocuments
    state: disabled
    settings:
      canonical_webroot: https://office.molecule.lan
      disable_certificate_verification: true
      edit_groups: "admin"
      public_wopi_url: https://office.molecule.lan
      use_groups: "admin"
      wopi_allowlist: "127.0.0.1/32"
      wopi_url: https://office.molecule.lan
```

---

## Contribution

Please read [Contribution](CONTRIBUTING.md)

## Development,  Branches (Git Tags)

The `master` Branch is my *Working Horse* includes the "latest, hot shit" and can be complete broken!

If you want to use something stable, please use a [Tagged Version](https://github.com/bodsch/ansible-nextcloud/-/tags)!

---

## Author and License

- Bodo Schulz

## License

[Apache](LICENSE)

**FREE SOFTWARE, HELL YEAH!**
