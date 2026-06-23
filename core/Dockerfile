FROM ubuntu:20.04 AS binwalk-builder
LABEL org.opencontainers.image.authors="Mingeun Kim <pr0v3rbs@kaist.ac.kr>, Minkyo Seo <0xsaika@gmail.com>"

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn \
    PIP_NO_CACHE_DIR=1

# for binwalk
COPY ./binaries/binwalk-2.3.4.tar.gz /tmp/binwalk-2.3.4.tar.gz
RUN set -eux; \
    sed -i 's@http://archive.ubuntu.com/ubuntu/@http://mirrors.tuna.tsinghua.edu.cn/ubuntu/@g; s@http://security.ubuntu.com/ubuntu/@http://mirrors.tuna.tsinghua.edu.cn/ubuntu/@g' /etc/apt/sources.list; \
    mkdir -p /etc/pip; \
    printf '[global]\nindex-url = https://pypi.tuna.tsinghua.edu.cn/simple\ntrusted-host = pypi.tuna.tsinghua.edu.cn\nno-cache-dir = true\n' > /etc/pip.conf; \
    printf 'Acquire::Languages "none";\n' > /etc/apt/apt.conf.d/99-no-translations; \
    printf 'APT::Install-Recommends "false";\nAPT::Install-Suggests "false";\n' > /etc/apt/apt.conf.d/99-no-recommends; \
    printf 'path-exclude=/usr/share/doc/*\npath-exclude=/usr/share/man/*\npath-exclude=/usr/share/info/*\npath-exclude=/usr/share/lintian/*\npath-exclude=/usr/share/linda/*\n' > /etc/dpkg/dpkg.cfg.d/01-no-docs; \
    apt-get update; \
    apt-get install -y ca-certificates wget tar python3 python3-dev python3-pip git build-essential zlib1g-dev liblzma-dev liblzo2-dev; \
    python3 -m pip install --upgrade pip; \
    mkdir -p /tmp/binwalk-2.3.4; \
    tar -xf /tmp/binwalk-2.3.4.tar.gz -C /tmp/binwalk-2.3.4 --strip-components=1; \
    cd /tmp/binwalk-2.3.4; \
    sed -i 's/^REQUIRED_UTILS="wget tar python"/REQUIRED_UTILS="wget tar python3"/g' deps.sh && \
    sed -i '/^function install_ubireader$/,/^}$/c\function install_ubireader\n{\n    $SUDO $PYTHON -mpip install ubi_reader==0.8.9\n}' deps.sh && \
    ./deps.sh --yes; \
    python3 setup.py install; \
    python3 -m pip install python-lzo cstruct ubi_reader==0.8.9; \
    python3 -m pip uninstall -y pycryptodome >/dev/null 2>&1 || true; \
    cd /; \
    rm -rf /tmp/binwalk-2.3.4 /tmp/binwalk-2.3.4.tar.gz; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* /root/.cache /tmp/pip-* /tmp/tmp*

FROM binwalk-builder AS project-files
WORKDIR /work/FirmAE
COPY . ./
RUN rm -f ./binaries/binwalk-2.3.4.tar.gz

FROM ubuntu:20.04
LABEL org.opencontainers.image.authors="Mingeun Kim <pr0v3rbs@kaist.ac.kr>, Minkyo Seo <0xsaika@gmail.com>"

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn \
    PIP_NO_CACHE_DIR=1 \
    USER=root \
    FIRMAE_DOCKER=true

RUN set -eux; \
    sed -i 's@http://archive.ubuntu.com/ubuntu/@http://mirrors.tuna.tsinghua.edu.cn/ubuntu/@g; s@http://security.ubuntu.com/ubuntu/@http://mirrors.tuna.tsinghua.edu.cn/ubuntu/@g' /etc/apt/sources.list; \
    mkdir -p /etc/pip; \
    printf '[global]\nindex-url = https://pypi.tuna.tsinghua.edu.cn/simple\ntrusted-host = pypi.tuna.tsinghua.edu.cn\nno-cache-dir = true\n' > /etc/pip.conf; \
    printf 'Acquire::Languages "none";\n' > /etc/apt/apt.conf.d/99-no-translations; \
    printf 'APT::Install-Recommends "false";\nAPT::Install-Suggests "false";\n' > /etc/apt/apt.conf.d/99-no-recommends; \
    printf 'path-exclude=/usr/share/doc/*\npath-exclude=/usr/share/man/*\npath-exclude=/usr/share/info/*\npath-exclude=/usr/share/lintian/*\npath-exclude=/usr/share/linda/*\n' > /etc/dpkg/dpkg.cfg.d/01-no-docs; \
    apt-get update; \
    mkdir -p /tmp/fuse-module-dummy/DEBIAN; \
    printf 'Package: fuse-module-dummy\nVersion: 1.0\nArchitecture: all\nMaintainer: FirmAE <noreply@example.invalid>\nProvides: fuse-module\nDescription: Dummy fuse-module provider for container builds\n' > /tmp/fuse-module-dummy/DEBIAN/control; \
    dpkg-deb --build /tmp/fuse-module-dummy /tmp/fuse-module-dummy.deb; \
    dpkg -i /tmp/fuse-module-dummy.deb; \
    rm -rf /tmp/fuse-module-dummy /tmp/fuse-module-dummy.deb; \
    apt-get install -y apt-utils; \
    apt-get install -y ca-certificates wget tar bc psmisc ruby telnet; \
    apt-get install -y socat net-tools iputils-ping iptables iproute2 curl; \
    apt-get install -yy python3 python3-pip; \
    apt-get install -y busybox-static bash-static fakeroot git kpartx netcat-openbsd uml-utilities util-linux vlan; \
    apt-get install -y mtd-utils gzip bzip2 tar arj lhasa p7zip p7zip-full cabextract fuse fusecram cramfsswap squashfs-tools sleuthkit default-jdk-headless cpio lzop lzma srecord zlib1g-dev liblzma-dev liblzo2-dev; \
    apt-get install -y python3-magic unrar; \
    apt-get install -y openjdk-8-jdk-headless; \
    apt-get install -y qemu-system-arm qemu-system-mips qemu-system-x86 qemu-utils; \
    apt-get install -y ntfs-3g; \
    ln -s /bin/ntfs-3g /bin/mount.ntfs-3g; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* /root/.cache /tmp/pip-* /tmp/tmp*

COPY --from=binwalk-builder /usr/local/ /usr/local/
WORKDIR /work/FirmAE
COPY --from=project-files /work/FirmAE/ ./
RUN install -m 777 ./core/sudo /usr/bin/sudo && \
    install -m 755 ./core/unstuff /usr/local/bin/unstuff && \
    mkdir -p /work/FirmAE/binaries /work/FirmAE/firmwares /work/firmwares
