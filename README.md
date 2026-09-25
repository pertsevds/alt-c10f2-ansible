# ALT Linux c10f2 Ansible Test Image

ALT Linux c10f2 Docker container for Ansible playbook and role testing, based on `registry.altlinux.org/alt/base:c10f2`.

## Container image

`ghcr.io/pertsevds/alt-c10f2-ansible:latest`

The published image path is `<repo>/<user>/alt-c10f2-ansible:latest`. Edit `IMAGE_REPO` (the registry host) and `IMAGE_USER` (the image owner) in the release job of `.github/workflows/build.yml` to change it. Their defaults are `ghcr.io` and `pertsevds`. The examples below use those defaults; substitute your configured path if you change them.

For a registry other than GHCR, set the GitHub Actions repository secrets `REGISTRY_USERNAME` and `REGISTRY_TOKEN` for an account that can push to the configured image path. GHCR uses the workflow's `GITHUB_TOKEN` by default.

## Tags

  - `latest`: Ansible from the ALT Linux c10f2 package repository.

## How to Build

GitHub Actions builds and tests the image on pull requests, pushes to `main`, and a weekly schedule. Builds from `main` are published to the configured registry. To build the image locally:

  1. [Install Docker](https://docs.docker.com/engine/installation/).
  2. `cd` into this directory.
  3. Run `docker build -t ghcr.io/pertsevds/alt-c10f2-ansible:latest .`

## How to Use

  Use it with [Molecule](https://github.com/ansible/molecule)

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
  
  1. [Install Docker](https://docs.docker.com/engine/installation/).
  2. Pull the default image from GHCR:
    `docker pull ghcr.io/pertsevds/alt-c10f2-ansible:latest`
    or use the image you built earlier.
  3. Run a container from the image:  
    `docker run --detach --privileged --volume=/sys/fs/cgroup:/sys/fs/cgroup:rw --cgroupns=host ghcr.io/pertsevds/alt-c10f2-ansible:latest` (to test my Ansible roles, I add in a volume mounted from the current working directory with ``--volume=`pwd`:/etc/ansible/roles/role_under_test:ro``).
  4. Use Ansible inside the container:  
    `docker exec --tty [container_id] env TERM=xterm ansible --version`  
    `docker exec --tty [container_id] env TERM=xterm ansible-playbook /path/to/ansible/playbook.yml --syntax-check`

## Notes

This image is adapted from https://github.com/geerlingguy/docker-debian12-ansible/.
