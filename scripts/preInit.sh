#!/firmadyne/sh

BUSYBOX=/firmadyne/busybox

firmae_set_aslr()
{
    FIRMAE_ASLR=`${BUSYBOX} cat /firmadyne/aslr 2>/dev/null || ${BUSYBOX} echo false`
    if [ -e /proc/sys/kernel/randomize_va_space ]; then
        if [ "${FIRMAE_ASLR}" = "true" ] || [ "${FIRMAE_ASLR}" = "1" ] || [ "${FIRMAE_ASLR}" = "yes" ]; then
            ${BUSYBOX} echo 1 > /proc/sys/kernel/randomize_va_space 2>/dev/null || true
        else
            ${BUSYBOX} echo 0 > /proc/sys/kernel/randomize_va_space 2>/dev/null || true
        fi
    fi
}

[ -d /dev ] || mkdir -p /dev
[ -d /root ] || mkdir -p /root
[ -d /sys ] || mkdir -p /sys
[ -d /proc ] || mkdir -p /proc
[ -d /tmp ] || mkdir -p /tmp
mkdir -p /var/lock

${BUSYBOX} mount -t sysfs sysfs /sys
${BUSYBOX} mount -t proc proc /proc
${BUSYBOX} ln -sf /proc/mounts /etc/mtab

firmae_set_aslr
(COUNT=0; while [ ${COUNT} -lt 300 ]; do firmae_set_aslr; COUNT=$((COUNT + 1)); ${BUSYBOX} sleep 1; done) &

mkdir -p /dev/pts
${BUSYBOX} mount -t devpts devpts /dev/pts
${BUSYBOX} mount -t tmpfs tmpfs /run
