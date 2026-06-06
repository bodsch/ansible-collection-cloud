 
# Ansible Role:  `bodsch.cloud.ical_backup`

Ansible role to install and configure [nextcloud-ical-backup](https://git.boone-schulz.de/go/nextcloud_ical_backup).

## usage

```yaml
ical_backup_version: "1.1.0"

ical_backup_user:
  group: ical_backup
  name: ical_backup
  home: /home/ical_backup

# ical_backup_system:
#   update: true
#   upgrade: false

ical_backup_arch:
  install_type: archive   # source | archive
  source_repository: https://codeberg.org/BernieO/ical_backup.git
  archive: "https://codeberg.org/BernieO/ical_backup/archive/v{{ ical_backup_version }}.tar.gz"

ical_backup_direct_download: false

ical_backup_config: {}

ical_backup_cron:
  type: systemd       # alternative cron or systemd
  daemon: ""          # "{{ 'cron' if ansible_os_family | lower == 'debian' else 'cronie' }}"
  enabled: true       # [true, false]
  cron:
    minute: "58"
    hour: "3"
    weekday: ""       # for systemd: 'Sat,Thu,Mon'
```

### `ical_backup_config`

```yaml
ical_backup_config:
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

### `ical_backup_cron`

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
ical_backup_cron:
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
ical_backup_cron:
  type: systemd
  daemon: ""
  enabled: true
  cron:
    minute: "58"
    hour: "3"
    weekday: ""

```

