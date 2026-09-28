FROM registry.altlinux.org/alt/base:c10f2

SHELL ["/bin/bash", "-xueo", "pipefail", "-c"]

ARG TARGETARCH

ENV LANG="C.UTF-8"
ENV pip_packages="ansible cryptography"

# Install dependencies.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache-"$TARGETARCH" \
    mkdir -p /var/cache/apt/archives/partial \
    && apt-get update \
    && apt-get dist-upgrade -y \
    && apt-get install -y \
       python3 python3-module-pip sudo systemd sysvinit-utils \
       wget procps \
       iproute2 dbus \
    && rm -rf /var/lib/apt/lists/* \
    && rm -Rf /usr/share/doc && rm -Rf /usr/share/man

# Install Ansible and cryptography.
RUN pip3 install --no-cache-dir $pip_packages

COPY initctl_faker /initctl_faker

RUN chmod +x initctl_faker && rm -fr /sbin/initctl && ln -s /initctl_faker /sbin/initctl \
    # Install Ansible inventory file.
    && mkdir -p /etc/ansible \
    && printf '[local]\nlocalhost ansible_connection=local\n' > /etc/ansible/hosts \
    # Make sure systemd doesn't start agettys on tty[1-6].
    && rm -f /lib/systemd/system/multi-user.target.wants/getty.target

VOLUME ["/sys/fs/cgroup", "/tmp", "/run", "/run/lock"]

CMD ["/sbin/systemd"]
