 
# Ansible Role:  `bodsch.cloud.nextcloud_apps`

Ansible role to install and configure nextcloud apps.


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
nextcloud_apps: []
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
    state: enabled
  #
  - name: event_update_notification
    state: enabled
  #
  - name: mail
    state: absent
    settings:
      antispam_reporting_ham: ""
      antispam_reporting_spam: ""
  #
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

## Author and License

- Bodo Schulz

## License

[Apache](LICENSE)

**FREE SOFTWARE, HELL YEAH!**
