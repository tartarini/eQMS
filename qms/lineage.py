"""Document lineage: for each version of a document, in order, what changed from the version
before, who approved and signed it, its history, and the document versions it is linked to.

Read-only: it reads the versions, signatures, links and audit trail, so it can't drift from
them. Links to documents the person can't see are left out, as the document list leaves them out.
"""
import re

from .access import accessible_devices, can_access
from .models import AuditEvent, DocumentVersion, Signature

APPROVAL = "Document approval"  # the meaning of the signature QA gives when approving a version


def approvals(version):
    return list(Signature.for_object(version).filter(meaning=APPROVAL).order_by("signed_at"))


def file_change(prev, version) -> str:
    """How the file differs from the previous version's file."""
    if not version.file:
        return "No file attached."
    if prev is None:
        return f"First file: {version.original_name}."
    if not prev.file:
        return f"File added: {version.original_name}."
    if version.original_name != prev.original_name:
        return f"File replaced: {prev.original_name} → {version.original_name}."
    if version.sha256 != prev.sha256:
        return f"File content changed (still {version.original_name})."
    return "File unchanged."


def hidden_refs(user) -> list:
    """References such as "SPEC-002 v1.0" for versions on teams this person is not on. A link
    event names its target, so these must not appear in the history of a visible version."""
    versions = (DocumentVersion.objects.filter(document__device__isnull=False)
                .exclude(document__device__in=accessible_devices(user))
                .values_list("document__number", "version"))
    return [f"{number} v{version}" for number, version in versions]


def _mentions(text, refs) -> bool:
    return any(re.search(rf"(?<![\w-]){re.escape(ref)}(?![\w.])", text) for ref in refs)


def event_view(event, hidden) -> dict:
    """An audit event as the page shows it. A link event that names a hidden document says so
    without naming it."""
    lines = event.change_lines
    if event.action in ("link", "unlink") and any(_mentions(text, hidden) for _, text in lines):
        lines = [("link", "to a document you cannot see")]
    return {"timestamp": event.timestamp, "actor_name": event.actor_name,
            "action": event.get_action_display(), "lines": lines, "comment": event.comment}


def build(document, user) -> dict:
    """The lineage of ``document`` as the person may see it."""
    hidden = hidden_refs(user)
    versions = list(document.versions.select_related("author", "change_request")
                    .order_by("created_at", "pk"))
    entries, prev = [], None
    for v in versions:
        links = []
        for link in v.outgoing_links.select_related("target__document__device"):
            if can_access(user, link.target.document.device):
                links.append({"link": link, "other": link.target, "outward": True,
                              "approvals": approvals(link.target), "removable": link.removable})
        for link in v.incoming_links.select_related("source__document__device"):
            if can_access(user, link.source.document.device):
                links.append({"link": link, "other": link.source, "outward": False,
                              "approvals": approvals(link.source), "removable": False})
        entries.append({
            "version": v,
            "previous": prev,
            "file_change": file_change(prev, v),
            "signatures": Signature.for_object(v).order_by("signed_at"),
            "links": links,
            "events": [event_view(ev, hidden) for ev in AuditEvent.for_object(v).order_by("id")],
        })
        prev = v
    return {
        "document": document,
        "entries": entries,
        "events": AuditEvent.for_object(document).order_by("id"),
    }
