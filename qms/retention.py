"""Retention of records and obsolete documents (ISO 13485 4.2.4 and 4.2.5).

Nothing is deleted in the QMS. This module works out how long each closed record and withdrawn
document must be kept: the longer of the device's expected lifetime and the minimum in
``QMS_RETENTION_MIN_YEARS``. Documents for QMS-wide procedures use the longest expected lifetime
of the active devices, so they are never released too early.

Retention runs from the date a record was closed or a document was withdrawn. That is never
earlier than the device's release, so the period is conservative.
"""
from datetime import date

from django.conf import settings
from django.db.models import Max

from . import workflow as wf
from .models import Device, Document, Record


def add_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:  # 29 February in a non-leap year
        return day.replace(year=day.year + years, month=3, day=1)


def longest_lifetime():
    return Device.objects.filter(active=True).aggregate(m=Max("expected_lifetime_years"))["m"]


def _lifetime(device):
    return device.expected_lifetime_years if device is not None else longest_lifetime()


def lifetime_defined(device) -> bool:
    return _lifetime(device) is not None


def retention_years(device) -> int:
    return max(settings.QMS_RETENTION_MIN_YEARS, _lifetime(device) or 0)


def retention_until(device, from_day: date) -> date:
    return add_years(from_day, retention_years(device))


def retention_items(within_days=None, today=None):
    """Closed records and withdrawn documents with the date their retention period ends.

    With ``within_days``, only items whose retention ends within that many days (or has already
    ended) are returned. Sorted by end date.
    """
    today = today or date.today()
    rows = []
    for record in Record.objects.filter(status__in=wf.TERMINAL_STATES,
                                        closed_at__isnull=False).select_related("device"):
        start = record.closed_at.date()
        rows.append({"kind": "Record", "ref": record.ref, "title": record.title,
                     "device": record.device.code, "from": start,
                     "until": retention_until(record.device, start),
                     "lifetime_defined": lifetime_defined(record.device)})
    for doc in Document.objects.filter(obsolete=True, obsolete_on__isnull=False).select_related(
            "device"):
        rows.append({"kind": "Document", "ref": doc.number, "title": doc.title,
                     "device": doc.device.code if doc.device else "QMS-wide",
                     "from": doc.obsolete_on,
                     "until": retention_until(doc.device, doc.obsolete_on),
                     "lifetime_defined": lifetime_defined(doc.device)})
    if within_days is not None:
        limit = today.toordinal() + within_days
        rows = [r for r in rows if r["until"].toordinal() <= limit]
    return sorted(rows, key=lambda r: r["until"])
