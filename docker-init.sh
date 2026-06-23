#!/bin/sh
set -e

./download.sh

DOCKER_BUILDKIT=0 docker build -t fcore -f ./core/Dockerfile .
echo "[*] Completed initializing core docker"
