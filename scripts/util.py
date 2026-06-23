#!/usr/bin/env python3

import sys
import hashlib
import json
import os


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
SCRATCH_DIR = os.environ.get("FIRMAE_SCRATCH_DIR", os.path.join(ROOT_DIR, "scratch"))
METADATA_FILE = "metadata.json"


def io_md5(target):
    blocksize = 65536
    hasher = hashlib.md5()

    with open(target, "rb") as ifp:
        buf = ifp.read(blocksize)
        while buf:
            hasher.update(buf)
            buf = ifp.read(blocksize)
        return hasher.hexdigest()


def iid_from_hash(md5):
    iid = int(md5[:8], 16) & 0x7FFFFFFF
    return str(iid or 1)


def get_iid(infile, _unused=None):
    return iid_from_hash(io_md5(infile))


def metadata_path(iid):
    return os.path.join(SCRATCH_DIR, str(iid), METADATA_FILE)


def read_metadata(iid):
    path = metadata_path(iid)
    if not os.path.exists(path):
        return {}

    try:
        with open(path) as fp:
            return json.load(fp)
    except (OSError, ValueError):
        return {}


def write_metadata(iid, values):
    path = metadata_path(iid)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    data = read_metadata(iid)
    data["id"] = str(iid)
    for key, value in values.items():
        if value is not None:
            data[key] = value

    with open(path, "w") as fp:
        json.dump(data, fp, indent=2, sort_keys=True)
        fp.write("\n")
    return data


def record_image(infile, brand=None):
    md5 = io_md5(infile)
    iid = iid_from_hash(md5)
    values = {
        "hash": md5,
        "filename": os.path.basename(infile),
        "path": os.path.abspath(infile),
    }
    if brand and brand != "auto":
        values["brand"] = brand
    write_metadata(iid, values)
    return iid


def update_metadata(iid, **values):
    return write_metadata(iid, values)


def get_brand(infile, _unused=None):
    iid = get_iid(infile)
    return read_metadata(iid).get("brand", "")


def check_connection(_unused=None):
    return 0


# command line
if __name__ == "__main__":
    if len(sys.argv) < 2:
        exit(1)

    if sys.argv[1] == "get_iid":
        print(get_iid(sys.argv[2]))
    elif sys.argv[1] == "record_image":
        brand = sys.argv[3] if len(sys.argv) > 3 else None
        print(record_image(sys.argv[2], brand))
    elif sys.argv[1] == "get_brand":
        print(get_brand(sys.argv[2]))
    elif sys.argv[1] == "check_connection":
        exit(check_connection())
    else:
        exit(1)
