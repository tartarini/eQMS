#!/usr/bin/env python3
"""Write or check the manifest of a backup folder (used by scripts/local.sh).

  backup_manifest.py write FOLDER LABEL DATABASE DBFILE   record the SHA-256 of each file
  backup_manifest.py verify FOLDER                         check the files against the manifest

The manifest has the same "files" map as the server's manifest (deploy/scripts/backup.sh), so
a folder copied from the server and a folder made on this machine are checked the same way.
Standard library only.
"""
import datetime
import hashlib
import json
import os
import subprocess
import sys


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write(folder, label, database, dbfile):
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    manifest = {
        "created_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "label": label,
        "database": database,
        "git_commit": commit,
        "files": {name: sha256(os.path.join(folder, name)) for name in (dbfile, "media.tar.gz")},
    }
    with open(os.path.join(folder, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


def verify(folder):
    with open(os.path.join(folder, "manifest.json")) as f:
        manifest = json.load(f)
    for name, expected in manifest["files"].items():
        if sha256(os.path.join(folder, name)) != expected:
            sys.exit(f"checksum mismatch for {name}: the backup is damaged or incomplete")
    print(f"checksums match the manifest ({', '.join(manifest['files'])})")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["write"] and len(args) == 5:
        write(*args[1:5])
    elif args[:1] == ["verify"] and len(args) == 2:
        verify(args[1])
    else:
        sys.exit(__doc__)
