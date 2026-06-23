#!/bin/bash

sudo apt update
sudo apt install -y curl wget tar git ruby python3 python3-pip bc
sudo python3 -m pip install --upgrade pip
sudo python3 -m pip install coloredlogs

# for docker
sudo apt install -y docker.io
sudo groupadd docker
sudo usermod -aG docker $USER

sudo apt install -y busybox-static bash-static fakeroot dmsetup kpartx netcat-openbsd uml-utilities util-linux vlan

# for binwalk
tar -xf ./binaries/binwalk-2.3.4.tar.gz && \
  cd binwalk-2.3.4 && \
  sed -i 's/^REQUIRED_UTILS="wget tar python"/REQUIRED_UTILS="wget tar python3"/g' deps.sh && \
  sed -i '/^function install_ubireader$/,/^}$/c\function install_ubireader\n{\n    $SUDO $PYTHON -mpip install ubi_reader==0.8.9\n}' deps.sh && \
  ./deps.sh --yes && \
  sudo python3 setup.py install
sudo apt install -y mtd-utils gzip bzip2 tar arj lhasa p7zip p7zip-full cabextract fusecram cramfsswap squashfs-tools sleuthkit default-jdk cpio lzop lzma srecord zlib1g-dev liblzma-dev liblzo2-dev unzip

cd - # back to root of project

sudo cp core/unstuff /usr/local/bin/

python3 -m pip install python-lzo cstruct ubi_reader==0.8.9
sudo apt install -y python3-magic openjdk-8-jdk unrar

# for qemu
sudo apt install -y qemu-system-arm qemu-system-mips qemu-system-x86 qemu-utils
