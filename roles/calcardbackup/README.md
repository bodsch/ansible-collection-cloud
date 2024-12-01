 
# Ansible Role:  `bodsch.cloud.calcardbackup`

Ansible role to install and configure [calcardbackup](https://codeberg.org/BernieO/calcardbackup).

## usage

```yaml
calcardbackup_version: "8.0.2"

calcardbackup_user:
  group: calcardbackup
  name: calcardbackup
  home: /home/calcardbackup

calcardbackup_system:
  update: true
  upgrade: false

calcardbackup_arch:
  install_type: archive   # source | archive
  source_repository: https://codeberg.org/BernieO/calcardbackup.git
  archive: "https://codeberg.org/BernieO/calcardbackup/archive/v{{ calcardbackup_version }}.tar.gz"

calcardbackup_direct_download: false

calcardbackup_config: {}

calcardbackup_cron:
  type: cron          # alternative and currently not supported: cron or systemd
  daemon: ""          # "{{ 'cron' if ansible_os_family | lower == 'debian' else 'cronie' }}"
  enabled: true       # [true, false]
  cron:
    minute: "58"
    hour: "3"
    weekday: ""       # for systemd: 'Sat,Thu,Mon'
```

### `calcardbackup_config`

```yaml
calcardbackup_config:
  nextcloud_path: "/usr/share/nginx/www/"
  nextcloud_url: "https://www.my_nextcloud.net"
  trustful_certificate: true
  users_file: ""
  backupfolder: "/backup/"
  date_extension: "-%Y-%m-%d"
  keep_days_like_time_machine: "0"
  delete_backups_older_than: "0"
  compress: true
  compression_method: "tar.gz"
  encrypt_backup: false
  gpg_passphrase: ""
  backup_addressbooks: true
  backup_calendars: true
  include_shares: true
  snap: false
  one_file_per_component: false
  read_mysql_optionfiles: true
  temporary_directory: ""
  mask: ""
```

### `calcardbackup_cron`

To create the cron Job.

| Variable       | default    | Description |
| :---           | :----      | :----       |
| `type`         | `webcron`  | alternative: `cron`.<br>systemd User can create an system timer with `systemd` insteed `cron` |
| `daemon`       | ` `        | the named cron package (Will be installed) |
| `enabled`      | `false`    | enable cron Background Jobs.    |
| `cron.minute`  | `*/5`      | cron configuration: *minute*    |
| `cron.hour`    | `*`        | cron configuration: *hour*      |
| `cron.weekday` | `*`        | cron configuration: *weekday*   |

#### example for cron

```yaml
calcardbackup_cron:
  type: cron
  daemon: "{{ 'cron' if ansible_os_family | lower == 'debian' else 'cronie' }}"
  enabled: true
  cron:
    minute: "58"
    hour: "3"
    weekday: "*"
```

#### example for systemd

```yaml
calcardbackup_cron:
  type: systemd
  daemon: ""
  enabled: true
  cron:
    minute: "58"
    hour: "3"
    weekday: ""

```

