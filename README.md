# Ansible Collection - bodsch.cloud

A collection of Ansible roles for Nextcloud and Tools.


[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-cloud/main.yml?branch=main)][ci]
[![GitHub issues](https://img.shields.io/github/issues/bodsch/ansible-collection-cloud)][issues]
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/bodsch/ansible-collection-cloud)][releases]

[ci]: https://github.com/bodsch/ansible-collection-cloud/actions
[issues]: https://github.com/bodsch/ansible-collection-cloud/issues?q=is%3Aopen+is%3Aissue
[releases]: https://github.com/bodsch/ansible-collection-cloud/releases


## supported operating systems

* Arch Linux
* Debian based
    - Debian 10 / 11
    - Ubuntu 20.10

## Contribution

Please read [Contribution](CONTRIBUTING.md)

## Development,  Branches (Git Tags)

The `master` Branch is my *Working Horse* includes the "latest, hot shit" and can be complete broken!

If you want to use something stable, please use a [Tagged Version](https://github.com/bodsch/ansible-collection-cloud/tags)!

---

## Roles

| Role                                                        | Build State | Description |
|:----------------------------------------------------------- | :---- | :---- |
| [bodsch.cloud.nextcloud](./roles/nextcloud/README.md)         | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-cloud/nextcloud.yml?branch=main)][nextcloud]       | Ansible role to install and configure `nextcloud`. |
| [bodsch.cloud.collabora](./roles/collabora/README.md)         | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-cloud/collabora.yml?branch=main)][collabora]       | Ansible role to install and configure `collabora`. |
| [bodsch.cloud.calcardbackup](./roles/calcardbackup/README.md) | [![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/bodsch/ansible-collection-cloud/calcardbackup.yml?branch=main)][calcardbackup] | Ansible role to install and configure `calcardbackup`. |


[nextcloud]: https://github.com/bodsch/ansible-collection-cloud/actions/workflows/nextcloud.yml
[collabora]: https://github.com/bodsch/ansible-collection-cloud/actions/workflows/collabora.yml
[calcardbackup]: https://github.com/bodsch/ansible-collection-cloud/actions/workflows/calcardbackup.yml
