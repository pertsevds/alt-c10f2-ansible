# ALT Linux c10f2 Ansible Test Image

ALT Linux c10f2 Docker container for Ansible playbook and role testing, based on `registry.altlinux.org/alt/base:c10f2`.

This image is a managed target for Molecule and Ansible. Run Molecule and Ansible on your computer or CI runner; the image provides Python 3, sudo, systemd, wget, process and network tools, and D-Bus. Ansible and cryptography are not installed by this image. Roles that need pip or cryptography should install them as target dependencies.

## Container image

`ghcr.io/pertsevds/alt-c10f2-ansible:latest`

The published image path is `<repo>/<user>/alt-c10f2-ansible:latest`. Edit `IMAGE_REPO` (the registry host) and `IMAGE_USER` (the image owner) in `.github/workflows/build.yml` to change it. Their defaults are `ghcr.io` and `pertsevds`. The examples below use those defaults; substitute your configured path if you change them.

For a registry other than GHCR, set the GitHub Actions repository secrets `REGISTRY_USERNAME` and `REGISTRY_TOKEN` for an account that can push to the configured image path. GHCR uses the workflow's `GITHUB_TOKEN` by default.

## Tags

  - `latest`: ALT Linux c10f2 managed target with the distribution's Python 3 and systemd.
  - `latest-amd64` and `latest-arm64`: Architecture images built on native GitHub runners and combined under `latest`.

## How to Build

GitHub Actions builds and tests the image on pull requests, pushes to `main`, and a weekly schedule. CI runs Ansible on the runner with Python 3.12 and connects to the container to test ping, fact gathering, and service management. Builds from `main` are published to the configured registry.

After a successful GHCR release, the workflow removes untagged package versions that are not referenced by any current image tag. The repository must have admin access to the GHCR package for deletion. This cleanup does not run for other registries.

To build the image locally:

  1. [Install Docker](https://docs.docker.com/engine/installation/).
  2. `cd` into this directory.
  3. Run `docker build -t ghcr.io/pertsevds/alt-c10f2-ansible:latest .`

## How to Use

  Use it with [Molecule](https://github.com/ansible/molecule)

Install Molecule, its Docker plugin, and Ansible on the controller. The target image does not contain an Ansible inventory; Molecule manages the inventory for your scenario.

```yml
dependency:
  name: galaxy

driver:
  name: docker

platforms:
  - name: alt-c10f2
    image: "ghcr.io/pertsevds/alt-c10f2-ansible:latest"
    pre_build_image: true
    privileged: true
    command: /sbin/systemd
    cgroupns_mode: host
    tmpfs:
      - /tmp
      - /run
      - /run/lock
    volumes:
      - /sys/fs/cgroup:/sys/fs/cgroup:rw
```
  
  or
  
  1. [Install Docker](https://docs.docker.com/engine/installation/) and Ansible on the controller. Ensure the Docker connection collection is available with `ansible-galaxy collection install community.docker`.
  2. Pull the default image from GHCR:
    `docker pull ghcr.io/pertsevds/alt-c10f2-ansible:latest`
    or use the image you built earlier.
  3. Run a container from the image:  
    `docker run --name alt-c10f2 --detach --privileged --volume=/sys/fs/cgroup:/sys/fs/cgroup:rw --cgroupns=host ghcr.io/pertsevds/alt-c10f2-ansible:latest`
  4. Run Ansible from the controller against the container:

```sh
ansible alt-c10f2 -i 'alt-c10f2,' -c community.docker.docker -u root \
  -e ansible_python_interpreter=/usr/bin/python3 -m ansible.builtin.ping
ansible-playbook -i 'alt-c10f2,' -c community.docker.docker -u root \
  -e ansible_python_interpreter=/usr/bin/python3 /path/to/playbook.yml
```

Use `hosts: all` or `hosts: alt-c10f2` in the playbook. Keep roles and playbooks on the controller. When finished, remove the container with `docker rm -f alt-c10f2`.

## Notes

This image is adapted from https://github.com/geerlingguy/docker-debian12-ansible/.
