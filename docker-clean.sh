#!/bin/bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SCRATCH_DIR="${ROOT_DIR}/scratch"
IMAGES_DIR="${ROOT_DIR}/images"
DRY_RUN=false

usage()
{
    echo "Usage: sudo $0 [--dry-run]"
    echo "Clean FirmAE emulation containers, network devices, mounts, and generated files."
}

run()
{
    printf '+'
    printf ' %q' "$@"
    printf '\n'

    if [ "${DRY_RUN}" = "false" ]; then
        "$@" || true
    fi
}

collect_iids()
{
    local entry
    IIDS=()

    if [ ! -d "${SCRATCH_DIR}" ]; then
        return
    fi

    for entry in "${SCRATCH_DIR}"/*; do
        [ -d "${entry}" ] || continue
        case "$(basename "${entry}")" in
            ''|*[!0-9]*)
                ;;
            *)
                IIDS+=("$(basename "${entry}")")
                ;;
        esac
    done
}

cleanup_docker()
{
    local name
    local image

    if ! command -v docker >/dev/null 2>&1; then
        return
    fi

    while read -r name image; do
        [ -n "${name}" ] || continue
        case "${name}:${image}" in
            firmae_*:*|docker[0-9]_*:*|*:fcore|*:fcore:*)
                run docker rm -f "${name}"
                ;;
        esac
    done < <(docker ps -a --format '{{.Names}} {{.Image}}' 2>/dev/null || true)
}

cleanup_processes()
{
    local iid
    local pid

    if ! command -v pgrep >/dev/null 2>&1; then
        return
    fi

    for iid in "${IIDS[@]}"; do
        while read -r pid; do
            [ -n "${pid}" ] || continue
            run kill "${pid}"
        done < <(pgrep -f "qemu\\.${iid}([^0-9]|$)|scratch/${iid}/run\\.sh|scratch/${iid}/run_(debug|analyze|boot)\\.sh" 2>/dev/null || true)
    done
}

cleanup_mounts()
{
    local mountpoint

    if command -v findmnt >/dev/null 2>&1; then
        while read -r mountpoint; do
            [ -n "${mountpoint}" ] || continue
            run umount -lf "${mountpoint}"
        done < <(findmnt -rn -o TARGET 2>/dev/null | awk -v root="${SCRATCH_DIR}" 'index($0, root "/") == 1 {print}' | sort -r)
    else
        while read -r mountpoint; do
            [ -n "${mountpoint}" ] || continue
            run umount -lf "${mountpoint}"
        done < <(awk '{print $2}' /proc/mounts 2>/dev/null | sed 's/\\040/ /g' | awk -v root="${SCRATCH_DIR}" 'index($0, root "/") == 1 {print}' | sort -r)
    fi
}

cleanup_loop_devices()
{
    local line
    local loop_dev
    local loop_name

    if ! command -v losetup >/dev/null 2>&1; then
        return
    fi

    while read -r line; do
        case "${line}" in
            *"(${SCRATCH_DIR}/"*"/image.raw)"*|*"${SCRATCH_DIR}/"*"/image.raw"*)
                loop_dev="${line%%:*}"
                loop_name="$(basename "${loop_dev}")"

                if command -v kpartx >/dev/null 2>&1; then
                    run kpartx -d "${loop_dev}"
                fi
                if command -v dmsetup >/dev/null 2>&1; then
                    run dmsetup remove "${loop_name}p1"
                fi
                run losetup -d "${loop_dev}"
                run rm -f "${loop_dev}"p[0-9]*
                ;;
        esac
    done < <(losetup -a 2>/dev/null || true)
}

cleanup_network()
{
    local dev

    if ! command -v ip >/dev/null 2>&1; then
        return
    fi

    while read -r dev; do
        [ -n "${dev}" ] || continue
        run ip link delete "${dev}"
    done < <(ip -o link show 2>/dev/null | awk -F': ' '{print $2}' | cut -d@ -f1 | grep -E '^tap[0-9]+_[0-9]+\.[0-9]+$' | sort -r || true)

    while read -r dev; do
        [ -n "${dev}" ] || continue
        run ip link delete "${dev}"
    done < <(ip -o link show 2>/dev/null | awk -F': ' '{print $2}' | cut -d@ -f1 | grep -E '^tap[0-9]+_[0-9]+$' | sort -r || true)
}

cleanup_qemu_sockets()
{
    local iid

    for iid in "${IIDS[@]}"; do
        run rm -f "/tmp/qemu.${iid}" "/tmp/qemu.${iid}.S1"
    done
}

cleanup_generated_files()
{
    local entries

    run mkdir -p "${SCRATCH_DIR}" "${IMAGES_DIR}" "${ROOT_DIR}/firmwares"
    shopt -s nullglob dotglob

    entries=("${SCRATCH_DIR}"/*)
    if [ "${#entries[@]}" -gt 0 ]; then
        run rm -rf "${entries[@]}"
    fi

    entries=("${IMAGES_DIR}"/*)
    if [ "${#entries[@]}" -gt 0 ]; then
        run rm -rf "${entries[@]}"
    fi

    shopt -u nullglob dotglob
    run mkdir -p "${SCRATCH_DIR}" "${IMAGES_DIR}" "${ROOT_DIR}/firmwares"
}

main()
{
    if [ "$#" -gt 1 ]; then
        usage
        exit 1
    fi

    if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
        usage
        exit 0
    elif [ "${1:-}" = "--dry-run" ]; then
        DRY_RUN=true
    elif [ "$#" -eq 1 ]; then
        usage
        exit 1
    fi

    if [ "$(id -u)" -ne 0 ]; then
        echo "Error: this script must run with root privileges. Try: sudo $0 ${1:-}" >&2
        exit 1
    fi

    collect_iids

    cleanup_docker
    cleanup_processes
    cleanup_mounts
    cleanup_loop_devices
    cleanup_network
    cleanup_qemu_sockets
    cleanup_generated_files

    echo "FirmAE emulation environment cleaned."
}

main "$@"
