#!/bin/sh

set -e

check_local_binary()
{
  binary_path="./binaries/${1}"
  if [ ! -s "${binary_path}" ]; then
    echo "Missing local binary: ${binary_path}" >&2
    return 1
  fi
}

check_local_kernel()
{
  kernel_path="./binaries/${1}"
  if [ ! -f "${kernel_path}" ]; then
    echo "Missing local kernel binary: ${kernel_path}" >&2
    return 1
  fi

  kernel_size=$(wc -c < "${kernel_path}")
  if [ "${kernel_size}" -lt 1048576 ]; then
    echo "Local kernel binary looks incomplete: ${kernel_path} (${kernel_size} bytes)" >&2
    return 1
  fi
}

check_local_tar_gz()
{
  archive_path="./binaries/${1}"
  check_local_binary "${1}" || return 1

  if ! tar -tzf "${archive_path}" >/dev/null; then
    echo "Local archive looks incomplete or invalid: ${archive_path}" >&2
    return 1
  fi
}

echo "Checking local binaries..."
missing_binary=false

for kernel in \
  vmlinux.mipsel.2 vmlinux.mipseb.2 vmlinux.mipsel.4 vmlinux.mipseb.4 \
  zImage.armel vmlinux.armel
do
  check_local_kernel "${kernel}" || missing_binary=true
done

for binary in \
  binwalk-2.3.4.tar.gz \
  busybox.armel busybox.mipseb busybox.mipsel \
  console.armel console.mipseb console.mipsel \
  libnvram.so.armel libnvram.so.mipseb libnvram.so.mipsel \
  libnvram_ioctl.so.armel libnvram_ioctl.so.mipseb libnvram_ioctl.so.mipsel \
  gdb.armel gdb.mipseb gdb.mipsel \
  gdbserver.armel gdbserver.mipseb gdbserver.mipsel \
  strace.armel strace.mipseb strace.mipsel
do
  check_local_binary "${binary}" || missing_binary=true
done

check_local_tar_gz binwalk-2.3.4.tar.gz || missing_binary=true

if [ "${missing_binary}" = "true" ]; then
  exit 1
fi

echo "All required local binaries are present."
