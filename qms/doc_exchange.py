"""Import and export of controlled documents as folders of files.

Export writes one folder per effective document, under the device it belongs to and its type:

    <device code or QMS>/<type>/<number> <title>/
        <number>.md          front matter (number, title, version, dates, owner) and the text
                             of the document if it is markdown; otherwise a pointer to the file
        <original file>      the effective file exactly as uploaded
    INDEX.md                 every exported document, one row each
    MANIFEST.json            sha256 of every file, so a folder can be synced by changes only

A folder can be kept up to date with ``sync_folder``, which writes only changed files and
removes files of documents that are no longer effective (their versions stay in the QMS).

Import reads markdown files (or a zip of them) with the same front matter. A new ``number`` is
created as a new document with a draft first version; an existing ``number`` gets a draft
revision, so an exported document can be edited outside the QMS and brought back in.
"""
import hashlib
import io
import json
import os
import re
import zipfile
from datetime import date

from django.core.files.base import ContentFile
from django.utils.text import slugify

from . import workflow as wf
from .access import accessible_devices
from .models import DOC_TYPES, Device, Document
from .services import TransitionError, create_version, user_has_role

MANIFEST = "MANIFEST.json"
INDEX = "INDEX.md"
MAX_IMPORT_BYTES = 2 * 1024 * 1024
MAX_IMPORT_FILES = 200


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _line(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _documents_for(user=None):
    docs = Document.objects.filter(obsolete=False).select_related("device", "owner")
    if user is not None:
        docs = docs.filter(device__in=accessible_devices(user)) | docs.filter(device__isnull=True)
    return docs


def _read_file(version) -> bytes:
    version.file.open("rb")
    try:
        return version.file.read()
    finally:
        version.file.close()


def export_files(user=None) -> dict:
    """{relative path: bytes} for every effective document the user can see (all, if no user)."""
    files, index_rows = {}, []
    for doc in _documents_for(user).order_by("number"):
        version = doc.effective_version
        if not version or not version.file:
            continue
        folder = "/".join([doc.device.code if doc.device else "QMS", doc.doc_type,
                           f"{doc.number} {slugify(doc.title) or doc.number}"])
        original = os.path.basename(version.original_name or version.file.name)
        data = _read_file(version)
        is_md = original.lower().endswith(".md")
        front = [
            "---",
            f"number: {doc.number}",
            f"title: {_line(doc.title)}",
            f"type: {doc.doc_type}",
            f"device: {doc.device.code if doc.device else ''}",
            f"version: {version.version}",
            f"effective_date: {version.effective_date or ''}",
            f"next_review: {version.next_review_date or ''}",
            f"owner: {doc.owner.get_username() if doc.owner else ''}",
            f"description: {_line(doc.description)}",
            "---", "",
        ]
        body = data.decode("utf-8", errors="replace") if is_md else (
            f"The controlled file for this document is attached as `{original}`.\n")
        files[f"{folder}/{doc.number}.md"] = ("\n".join(front) + body).encode("utf-8")
        files[f"{folder}/{original}"] = data
        index_rows.append((doc, version, folder))

    lines = ["# Controlled documents", "",
             f"Exported {date.today():%d %b %Y}. Each folder holds the effective version.", "",
             "| Number | Title | Device | Type | Version | Effective | Next review | Folder |",
             "|---|---|---|---|---|---|---|---|"]
    for doc, version, folder in index_rows:
        lines.append(f"| {doc.number} | {_line(doc.title)} | "
                     f"{doc.device.code if doc.device else 'QMS'} | {doc.doc_type} | "
                     f"{version.version} | {version.effective_date or ''} | "
                     f"{version.next_review_date or ''} | [{folder}]({folder}/) |")
    files[INDEX] = ("\n".join(lines) + "\n").encode("utf-8")
    files[MANIFEST] = json.dumps({p: _sha(d) for p, d in sorted(files.items())},
                                 indent=2).encode("utf-8")
    return files


def export_zip(user=None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, data in sorted(export_files(user).items()):
            zf.writestr(path, data)
    return buf.getvalue()


def sync_folder(root: str) -> dict:
    """Make ``root`` match the QMS: write changed files, remove files of documents that are no
    longer effective. Returns counts. Only files listed in the previous manifest are removed."""
    files = export_files()
    manifest_path = os.path.join(root, MANIFEST)
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            previous = set(json.load(fh))
    except (OSError, ValueError):
        previous = set()
    written = removed = unchanged = 0
    for path, data in files.items():
        full = os.path.join(root, path)
        if os.path.exists(full):
            with open(full, "rb") as fh:
                if _sha(fh.read()) == _sha(data):
                    unchanged += 1
                    continue
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as fh:
            fh.write(data)
        written += 1
    for path in sorted(previous - set(files)):
        full = os.path.join(root, path)
        if os.path.isfile(full):
            os.remove(full)
            removed += 1
            folder = os.path.dirname(full)
            while folder != os.path.abspath(root) and os.path.isdir(folder) and not os.listdir(folder):
                os.rmdir(folder)
                folder = os.path.dirname(folder)
    return {"written": written, "unchanged": unchanged, "removed": removed}


def sync_git(repo: str, push: bool = False) -> dict:
    """Sync ``repo`` (a git clone) with the QMS, commit the changes if there are any, and push
    if asked. Returns the sync counts and whether a commit was made."""
    import subprocess
    if not os.path.isdir(os.path.join(repo, ".git")):
        raise ValueError(f"{repo} is not a git clone. Clone the documents repository there first.")

    def git(*args):
        return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True,
                              text=True).stdout

    counts = sync_folder(repo)
    git("add", "-A")
    if not git("status", "--porcelain").strip():
        return {**counts, "committed": False, "pushed": False}
    git("-c", "user.name=SAMD_QMS export", "-c", "user.email=qms-export@localhost",
        "commit", "-m", f"Sync controlled documents ({date.today():%Y-%m-%d})")
    if push:
        git("push")
    return {**counts, "committed": True, "pushed": push}


# --- import ----------------------------------------------------------------------

def parse_markdown(text: str):
    """(front matter dict, body). Front matter is the ``key: value`` block between two ``---``
    lines at the top of the file; without one, the whole text is the body."""
    meta, body = {}, text
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            for line in text[4:end].splitlines():
                key, sep, value = line.partition(":")
                if sep and key.strip():
                    meta[key.strip().lower()] = value.strip()
            body = text[end + 4:].lstrip("\n")
    return meta, body


def _markdown_files(uploads):
    """(name, bytes) for each markdown file in the uploads, opening zips. Size-limited."""
    out = []
    for name, data in uploads:
        if name.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for info in zf.infolist():
                    if info.is_dir() or not info.filename.lower().endswith(".md"):
                        continue
                    if info.file_size > MAX_IMPORT_BYTES:
                        raise TransitionError([f"{info.filename} is larger than 2 MB."])
                    out.append((os.path.basename(info.filename), zf.read(info)))
        elif name.lower().endswith(".md"):
            out.append((os.path.basename(name), data))
        else:
            raise TransitionError([f"{name}: only .md files and .zip archives of them can be "
                                   "imported."])
        if len(out) > MAX_IMPORT_FILES:
            raise TransitionError([f"Import at most {MAX_IMPORT_FILES} files at a time."])
    return out


def import_markdown(user, uploads) -> list:
    """Create documents (or draft revisions) from markdown files. Returns (name, outcome) rows.
    Each file is imported on its own; a file with problems is reported and skipped."""
    from .access import can_access
    results = []
    for name, data in _markdown_files(uploads):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            results.append((name, "Not UTF-8 text; skipped."))
            continue
        meta, body = parse_markdown(text)
        try:
            results.append((name, _import_one(user, name, meta, body, data, can_access)))
        except TransitionError as exc:
            results.append((name, "; ".join(exc.errors)))
    return results


def _import_one(user, name, meta, body, data, can_access) -> str:
    number = meta.get("number", "")
    existing = Document.objects.filter(number=number).first() if number else None
    if existing is not None:
        if existing.obsolete:
            raise TransitionError([f"{number} is obsolete."])
        if not can_access(user, existing.device):
            raise TransitionError([f"You are not on {existing.device}'s team."])
        version = create_version(existing, user,
                                 version=existing.suggest_next_version(),
                                 change_summary="Imported from markdown",
                                 file=ContentFile(data, name=name))
        return f"Draft revision {version.version} of {existing.number} created."

    title = _line(meta.get("title", ""))
    doc_type = meta.get("type", "").upper()
    types = [code for code, _label in DOC_TYPES]
    if not title:
        raise TransitionError(["Front matter needs a title."])
    if doc_type not in types:
        raise TransitionError([f"Front matter needs a type: {', '.join(types)}."])
    code = meta.get("device", "").strip().upper()
    device = Device.objects.filter(code=code).first() if code else None
    if device is not None and not can_access(user, device):
        raise TransitionError([f"You are not on {device.name}'s team."])
    if device is None and code:
        raise TransitionError([f"No device with code {code}."])
    if device is None and not user_has_role(user, wf.ANY_ROLE):
        raise TransitionError(["Only a working role can create QMS-wide documents."])
    try:
        review_months = int(meta.get("review_months", "") or 0) or None
    except ValueError:
        review_months = None
    doc = Document.objects.create(
        title=title, doc_type=doc_type, device=device, owner=user,
        description=_line(meta.get("description", "")),
        review_period_months=review_months or 12,
    )
    create_version(doc, user, version="1.0", change_summary="Imported from markdown",
                   file=ContentFile(data, name=name))
    return f"New document {doc.number} created with a draft first version."
