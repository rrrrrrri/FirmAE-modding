#!/usr/bin/env python3

import getopt
import hashlib
import json
import os
import re
import sys
import tarfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from scripts import util


def file_hash(tar, member):
    hasher = hashlib.md5()
    fp = tar.extractfile(member)
    if not fp:
        return None

    while True:
        buf = fp.read(65536)
        if not buf:
            break
        hasher.update(buf)
    return hasher.hexdigest()


def get_file_hashes(infile):
    files = []
    links = []
    with tarfile.open(infile) as tar:
        for member in tar.getmembers():
            name = member.name[1:] if member.name.startswith(".") else member.name
            if member.isfile():
                digest = file_hash(tar, member)
                if digest:
                    files.append(
                        {
                            "filename": name,
                            "hash": digest,
                            "uid": member.uid,
                            "gid": member.gid,
                            "mode": member.mode,
                        }
                    )
            elif member.issym():
                links.append({"filename": name, "target": member.linkpath})
    return files, links


def process(iid, infile):
    files, links = get_file_hashes(infile)
    scratch_dir = os.path.join(util.SCRATCH_DIR, str(iid))
    os.makedirs(scratch_dir, exist_ok=True)

    manifest = {
        "iid": str(iid),
        "tarball": os.path.abspath(infile),
        "files": files,
        "links": links,
    }
    manifest_path = os.path.join(scratch_dir, "filesystem.json")
    with open(manifest_path, "w") as fp:
        json.dump(manifest, fp, indent=2, sort_keys=True)
        fp.write("\n")

    util.update_metadata(
        iid,
        filesystem_manifest=manifest_path,
        filesystem_file_count=len(files),
        filesystem_link_count=len(links),
    )


def main():
    infile = iid = None
    opts, _argv = getopt.getopt(sys.argv[1:], "f:i:h:")
    for k, v in opts:
        if k == "-i":
            iid = int(v)
        if k == "-f":
            infile = v

    if infile and not iid:
        m = re.search(r"(\d+)\.tar\.gz", infile)
        if m:
            iid = int(m.group(1))

    if not infile or not iid:
        print("Usage: tar2db.py -i <image ID> -f <rootfs tarball>", file=sys.stderr)
        exit(1)

    process(iid, infile)


if __name__ == "__main__":
    main()
