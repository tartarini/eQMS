"""
Technical file generation for one device.

The file follows the structure of EU MDR Annex II (technical documentation) and Annex III
(post-market surveillance), which the UK framework mirrors. Content comes from the QMS itself:
the device register, effective controlled documents tagged with a technical file section, the
risk register, the SOUP list, change and release history, open anomalies and PMS records.

``build_outline`` turns the data into a list of blocks; the same blocks render to HTML and Word,
so both outputs always agree. ``generate_technical_file`` packages everything into a ZIP with the
evidence files, CSV registers and a checksummed manifest, and stores it as a frozen build.
"""
import csv
import hashlib
import html
import io
import json
import os
import zipfile
from collections import defaultdict
from datetime import date

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from . import workflow as wf
from .models import (LEVEL_LABELS, TECH_FILE_SECTIONS, AuditEvent, Device, DocumentVersion,
                     Organisation, Record, Signature, TechnicalFileBuild, sha256_of, verify_audit_chain)

SECTION_LABELS = dict(TECH_FILE_SECTIONS)
SECTION_NUMBERS = {"description": "1", "labelling": "2", "design": "3", "gspr": "4",
                   "risk": "5", "verification": "6", "clinical": "6", "pms": "7",
                   "declaration": "8"}
# Sections that should hold at least one effective document, and how serious a gap is.
EXPECTED_SECTIONS = [
    ("labelling", "Instructions for use and labelling"),
    ("design", "Software development plan, requirements and architecture"),
    ("gspr", "General safety and performance requirements checklist"),
    ("risk", "Risk management plan and report"),
    ("verification", "Software verification and validation reports"),
    ("clinical", "Clinical evaluation (and usability) report"),
    ("pms", "Post-market surveillance plan"),
]


# ---------------------------------------------------------------------------
# Gathering data
# ---------------------------------------------------------------------------

def _effective_docs(device, section):
    """Effective versions of device-specific or QMS-wide documents tagged with ``section``."""
    return list(DocumentVersion.objects.filter(
        status="effective", document__obsolete=False, document__tech_file_section=section)
        .filter(Q(document__device=device) | Q(document__device__isnull=True))
        .select_related("document").order_by("document__number"))


def _doc_path(version):
    section = version.document.tech_file_section or "other"
    name = version.original_name or "file"
    return f"documents/{section}/{version.document.number}_v{version.version}_{name}"


def _version_approvals(version):
    sigs = Signature.objects.filter(object_type="Document Version", object_ref=version.audit_ref,
                                    meaning="Document approval")
    return ", ".join(f"{s.signer_name} {s.signed_at:%d %b %Y}" for s in sigs) or "—"


def gather(device: Device) -> dict:
    today = date.today()
    hazards = list(device.hazards.exclude(status="retired").prefetch_related(
        "controls__implemented_by").order_by("ref"))
    records = Record.objects.filter(device=device)
    open_records = records.exclude(status__in=wf.TERMINAL_STATES)

    releases = defaultdict(list)
    for cr in records.filter(record_type=wf.CHANGE_REQUEST, status="closed").order_by("closed_at"):
        releases[cr.fix_version or "unversioned"].append(cr)
    release_rows = sorted(releases.items(), key=lambda kv: max(c.closed_at for c in kv[1]),
                          reverse=True)

    sections = {code: _effective_docs(device, code) for code, _ in TECH_FILE_SECTIONS if code}
    tagged_docs = device.documents.exclude(tech_file_section="").filter(obsolete=False)
    return {
        "device": device,
        "organisation": Organisation.current(),
        "today": today,
        "sections": sections,
        "docs_without_effective": [d for d in tagged_docs if not d.effective_version],
        "qms_docs": list(DocumentVersion.objects.filter(
            status="effective", document__device__isnull=True, document__obsolete=False)
            .select_related("document").order_by("document__number")),
        "hazards": hazards,
        "soup": list(device.soup_items.filter(active=True).select_related("supplier")),
        "releases": release_rows,
        "open_anomalies": list(open_records.filter(record_type=wf.PROBLEM_REPORT)
                               .order_by("ref")),
        "complaints": list(records.filter(record_type=wf.COMPLAINT).order_by("created_at")),
        "incidents": list(records.filter(record_type=wf.INCIDENT).order_by("created_at")),
        "capas": list(records.filter(record_type=wf.CAPA).order_by("created_at")),
        "pms_done": list(records.filter(record_type=wf.PMS_ACTIVITY, status="done")
                         .order_by("-due_date")),
        "pms_open": list(open_records.filter(record_type=wf.PMS_ACTIVITY).order_by("due_date")),
        "overdue": [r for r in open_records if r.is_overdue],
        "builds": list(device.technical_files.all()),
    }


# ---------------------------------------------------------------------------
# Completeness checks
# ---------------------------------------------------------------------------

def completeness_checks(device: Device, data: dict = None) -> list:
    """List of {"level": "error"|"warning", "section", "message"}. Errors block approval."""
    data = data or gather(device)
    out = []

    def add(level, section, message):
        out.append({"level": level, "section": SECTION_NUMBERS.get(section, section),
                    "message": message})

    for field, label in [("intended_purpose", "Intended purpose"),
                         ("manufacturer", "Legal manufacturer"),
                         ("description", "Device description")]:
        if not getattr(device, field).strip():
            add("error", "1", f"{label} is missing from the device record.")
    if not device.operator_role_list():
        add("warning", "1", "Our economic operator role for this device (manufacturer, "
                            "authorised representative, importer or distributor) is not set.")
    if device.classification == "tbd":
        add("error", "1", "Device classification has not been determined.")
    elif not device.classification_rule.strip():
        add("warning", "1", "Classification rationale (rule applied) is missing.")
    if not device.software_safety_class:
        add("error", "3", "IEC 62304 software safety class is not set.")
    for field, label in [("basic_udi_di", "Basic UDI-DI"), ("current_version",
                         "Current software version"), ("standards_applied", "Standards applied"),
                         ("intended_users", "Intended users"),
                         ("software_items", "Software items (architecture)"),
                         ("patient_population", "Intended patient population")]:
        if not getattr(device, field).strip():
            add("warning", "1", f"{label} is not recorded.")

    for code, what in EXPECTED_SECTIONS:
        if not data["sections"].get(code):
            add("warning", code, f"No effective document in '{SECTION_LABELS[code]}' "
                                 f"(expected: {what}).")
    if not data["sections"].get("declaration"):
        level = "error" if device.regulatory_status == "on_market" else "warning"
        add(level, "8", "No effective Declaration of Conformity.")
    for d in data["docs_without_effective"]:
        add("warning", d.tech_file_section, f"{d.number} {d.title} has no effective version yet.")
    for section_docs in data["sections"].values():
        for v in section_docs:
            if v.document.review_overdue:
                add("warning", v.document.tech_file_section,
                    f"{v.document.number} is overdue for periodic review.")
            if not v.verify():
                add("error", v.document.tech_file_section,
                    f"{v} failed its integrity check; the stored file has changed.")

    hazards = data["hazards"]
    if not hazards:
        add("error", "5", "The risk register has no hazards for this device.")
    for h in hazards:
        level = h.residual_level or h.initial_level
        if h.status != "accepted":
            sev = "error" if level == "unacceptable" else "warning"
            add(sev, "5", f"{h.ref} {h.title}: residual risk not yet accepted"
                          f"{' and currently unacceptable' if level == 'unacceptable' else ''}.")
        unverified = [c for c in h.controls.all() if not c.verified]
        if unverified:
            add("warning", "5", f"{h.ref}: {len(unverified)} risk control(s) not verified.")

    if not data["soup"]:
        add("warning", "3", "No SOUP items are linked to this device.")
    stale = [s for s in data["soup"] if s.review_overdue]
    if stale:
        add("warning", "3", f"{len(stale)} SOUP item(s) overdue for anomaly review: "
                            + ", ".join(str(s) for s in stale[:5]))

    for r in data["open_anomalies"]:
        if r.patient_safety_impact == "yes":
            add("warning", "3", f"{r.ref} {r.title}: open problem with patient-safety impact.")
    for r in data["incidents"]:
        if r.status not in wf.TERMINAL_STATES:
            add("warning", "7", f"{r.ref} {r.title}: incident still open ({r.get_status_display()}).")
    for r in data["overdue"]:
        add("warning", "7", f"{r.ref} {r.title}: overdue since {r.next_deadline:%d %b %Y}.")

    ok, bad_id = verify_audit_chain()
    if not ok:
        add("error", "A", f"Audit trail integrity check failed at event {bad_id}.")
    return out


# ---------------------------------------------------------------------------
# Outline: one structure, rendered to HTML and Word
# ---------------------------------------------------------------------------

def _d(value):
    if value in (None, ""):
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%d %b %Y")
    return str(value)


def build_outline(device: Device, data: dict, checks: list, meta: dict) -> list:
    """Blocks: ("h1"|"h2"|"p"|"note", text), ("kv", [(k, v)]), ("table", headers, rows)."""
    B = []
    h1 = lambda t: B.append(("h1", t))  # noqa: E731
    h2 = lambda t: B.append(("h2", t))  # noqa: E731
    p = lambda t: B.append(("p", t))  # noqa: E731
    note = lambda t: B.append(("note", t))  # noqa: E731

    def table(headers, rows, empty="None."):
        if rows:
            B.append(("table", headers, [[_d(c) for c in r] for r in rows]))
        else:
            p(empty)

    def docs(section):
        versions = data["sections"].get(section, [])
        table(["Document", "Title", "Version", "Effective", "Approved by", "File (SHA-256)"],
              [[v.document.number, v.document.title, v.version, v.effective_date,
                _version_approvals(v), f"{_doc_path(v)} ({v.sha256[:16]}…)"] for v in versions],
              empty="No effective documents are tagged for this section.")

    errors = [c for c in checks if c["level"] == "error"]
    warnings = [c for c in checks if c["level"] == "warning"]

    # Cover
    B.append(("title", f"Technical Documentation – {device.name}"))
    B.append(("kv", [
        ("Technical file", meta["label"]),
        ("Device", f"{device.name} ({device.code})"),
        ("Software version", device.current_version),
        ("Classification", device.get_classification_display()),
        ("Regulatory status", device.get_regulatory_status_display()),
        ("Generated", f"{meta['generated_at']:%d %b %Y %H:%M} by {meta['generated_by']}"),
        ("Completeness", f"{len(errors)} error(s), {len(warnings)} warning(s)"),
    ]))
    note("Structure follows EU MDR (EU) 2017/745 Annex II and III. Content is generated from "
         "SAMD_QMS records; controlled documents are included at their effective versions. "
         "This file is a controlled build: changes require a new build.")

    # 1
    org = data.get("organisation")
    h1("1. Device description and specification")
    B.append(("kv", [
        ("Device name", device.name),
        ("Basic UDI-DI", device.basic_udi_di),
        ("Current software version", device.current_version),
        ("Intended purpose", device.intended_purpose),
        ("Intended users", device.intended_users),
        ("Intended patient population", device.patient_population),
        ("Contraindications and limitations", device.contraindications),
        ("Description and principle of operation", device.description),
        ("Classification", device.get_classification_display()),
        ("Classification rationale", device.classification_rule),
        ("IEC 62304 software safety class", device.get_software_safety_class_display()),
        ("Software items", ", ".join(device.software_item_list())),
        ("Organisation", org.name_and_address() if org else ""),
        ("Organisation SRN", org.srn if org else ""),
        ("Organisation's role for this device", ", ".join(device.operator_role_labels())),
        ("Legal manufacturer", device.manufacturer),
        ("UK Responsible Person / authorised representative", device.uk_responsible_person),
        ("Approved / notified body", device.approved_body),
        ("Markets", device.markets),
        ("Regulatory status", device.get_regulatory_status_display()),
    ]))
    h2("Supporting documents")
    docs("description")

    # 2
    h1("2. Information supplied by the manufacturer")
    p("Labels and instructions for use, at their effective versions.")
    docs("labelling")

    # 3
    h1("3. Design and manufacturing information")
    h2("Design documentation")
    docs("design")
    h2("Quality management system procedures")
    p("QMS-wide procedures in force at the time of this build.")
    table(["Document", "Title", "Version", "Effective"],
          [[v.document.number, v.document.title, v.version, v.effective_date]
           for v in data["qms_docs"]])
    h2("Software of unknown provenance (SOUP)")
    table(["Item", "Version", "Supplier", "Used in", "Safety class", "Licence",
           "Last anomaly review", "Known anomalies"],
          [[s.name, s.version, s.supplier, s.software_item, s.safety_class,
            s.licence, s.last_anomaly_review, s.known_anomalies] for s in data["soup"]])
    h2("Release and change history")
    rows = []
    for version, crs in data["releases"]:
        for cr in crs:
            rows.append([version, cr.ref, cr.title, cr.closed_at, cr.verification_evidence])
    table(["Version", "Change Request", "Change", "Closed", "Verification evidence"], rows,
          empty="No closed Change Requests.")
    h2("Known residual anomalies")
    p("Open Problem Reports at the time of this build (IEC 62304 §5.8.3).")
    table(["Ref", "Problem", "Status", "Severity", "Patient-safety impact", "Version found"],
          [[r.ref, r.title, r.get_status_display(), r.get_severity_display(),
            r.get_patient_safety_impact_display(), r.software_version]
           for r in data["open_anomalies"]])

    # 4
    h1("4. General safety and performance requirements")
    h2("Standards applied")
    standards = [s.strip() for s in device.standards_applied.splitlines() if s.strip()]
    table(["Standard"], [[s] for s in standards], empty="No standards recorded.")
    h2("GSPR checklist and evidence")
    docs("gspr")

    # 5
    h1("5. Benefit-risk analysis and risk management")
    docs("risk")
    h2("Risk register summary")
    hz = data["hazards"]
    count = lambda pred: sum(1 for h in hz if pred(h))  # noqa: E731
    table(["", "Acceptable", "Reduce as far as possible", "Unacceptable"], [
        ["Before controls"] + [count(lambda h, lv=lv: h.initial_level == lv)
                               for lv in ("acceptable", "alarp", "unacceptable")],
        ["Residual"] + [count(lambda h, lv=lv: h.residual_level == lv)
                        for lv in ("acceptable", "alarp", "unacceptable")],
    ])
    p(f"{len(hz)} active hazard(s); {count(lambda h: h.status == 'accepted')} with signed "
      "acceptance of residual risk.")
    h2("Hazards")
    table(["Ref", "Hazard", "Hazardous situation", "Harm", "Initial (S×P)", "Residual (S×P)",
           "Status"],
          [[h.ref, f"{h.title}: {h.hazard}", h.hazardous_situation, h.harm,
            f"{h.severity_initial}×{h.probability_initial} = {h.initial_score} "
            f"({LEVEL_LABELS.get(h.initial_level, '')})",
            (f"{h.severity_residual}×{h.probability_residual} = {h.residual_score} "
             f"({LEVEL_LABELS.get(h.residual_level, '')})") if h.residual_score else "—",
            h.get_status_display()] for h in hz])
    h2("Risk controls and verification")
    table(["Hazard", "Control", "Type", "Implemented by", "Verified", "Evidence"],
          [[h.ref, c.description, c.get_control_type_display(),
            c.implemented_by.ref if c.implemented_by else "", "Yes" if c.verified else "No",
            c.verification_evidence] for h in hz for c in h.controls.all()])
    rationales = [(h.ref, h.benefit_risk_rationale) for h in hz if h.benefit_risk_rationale]
    if rationales:
        h2("Benefit-risk rationales")
        table(["Hazard", "Rationale"], rationales)
    acceptances = Signature.objects.filter(object_type="Hazard",
                                           object_ref__in=[h.ref for h in hz],
                                           meaning="Risk acceptance")
    h2("Risk acceptance signatures")
    table(["Hazard", "Signed by", "Date", "Comment"],
          [[s.object_ref, s.signer_name, s.signed_at, s.comment] for s in acceptances])

    # 6
    h1("6. Product verification and validation")
    h2("Verification and validation reports")
    docs("verification")
    h2("Clinical evaluation and usability")
    docs("clinical")

    # 7
    h1("7. Post-market surveillance")
    docs("pms")
    h2("Completed PMS activities")
    table(["Ref", "Activity", "Period", "Findings"],
          [[r.ref, r.pms_schedule.name if r.pms_schedule else r.title,
            f"{_d(r.period_start)} – {_d(r.period_end)}", r.investigation_summary]
           for r in data["pms_done"]])
    h2("Scheduled PMS activities")
    table(["Ref", "Activity", "Due", "Status"],
          [[r.ref, r.title, r.due_date, r.get_status_display()] for r in data["pms_open"]])
    h2("Complaints")
    table(["Ref", "Complaint", "Date aware", "Status", "Reportable", "Rationale"],
          [[r.ref, r.title, r.date_aware, r.get_status_display(), r.get_reportable_display(),
            r.reportability_rationale] for r in data["complaints"]])
    h2("Incidents and vigilance reports")
    table(["Ref", "Incident", "Date aware", "Report due", "MHRA reference", "Status"],
          [[r.ref, r.title, r.date_aware, r.report_due, r.mhra_reference,
            r.get_status_display()] for r in data["incidents"]])
    h2("Corrective and preventive actions")
    table(["Ref", "CAPA", "Status", "Root cause", "Outcome"],
          [[r.ref, r.title, r.get_status_display(), r.root_cause, r.resolution]
           for r in data["capas"]])

    # 8
    h1("8. Declaration of conformity")
    docs("declaration")

    # Annex
    h1("Annex A. Completeness check")
    if checks:
        table(["Level", "Section", "Finding"],
              [[c["level"].upper(), c["section"], c["message"]] for c in checks])
    else:
        p("No gaps found.")
    h1("Annex B. Previous technical file builds")
    table(["Build", "Generated", "By", "Status", "SHA-256"],
          [[b.label, b.generated_at, b.generated_by, b.get_status_display(), b.sha256[:16] + "…"]
           for b in data["builds"]], empty="This is the first build.")
    return B


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

HTML_CSS = """
body{font:14px/1.5 Georgia,'Times New Roman',serif;color:#1d1d1b;max-width:1000px;margin:0 auto;padding:32px 24px}
h1.title{font:700 28px/1.2 system-ui,sans-serif;margin:0 0 16px}
h1{font:700 20px/1.3 system-ui,sans-serif;margin:36px 0 8px;padding-top:12px;border-top:2px solid #1d1d1b}
h2{font:600 16px/1.3 system-ui,sans-serif;margin:22px 0 6px}
table{width:100%;border-collapse:collapse;margin:8px 0 14px;font-size:12.5px}
th,td{border:1px solid #c9c8c2;padding:5px 7px;text-align:left;vertical-align:top;white-space:pre-wrap;overflow-wrap:anywhere}
th{background:#f0efec;font-family:system-ui,sans-serif}
table.kv th{width:30%}
.note{background:#f7f7f5;border-left:3px solid #1f5f8b;padding:8px 12px;font-size:13px}
.banner{background:#f9eeda;border:1px solid #b26a00;padding:10px 14px;font:600 14px system-ui,sans-serif;margin-bottom:20px}
@media print{body{padding:0;max-width:none}h1{break-before:page;border-top:0}h1.title{break-before:auto}tr{break-inside:avoid}.banner{border-width:2px}}
"""


def to_html(blocks, title, banner=""):
    e = html.escape
    out = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{e(title)}</title>"
           f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<style>{HTML_CSS}</style></head><body>"]
    if banner:
        out.append(f"<div class='banner'>{e(banner)}</div>")
    for block in blocks:
        kind = block[0]
        if kind == "title":
            out.append(f"<h1 class='title'>{e(block[1])}</h1>")
        elif kind in ("h1", "h2"):
            out.append(f"<{kind}>{e(block[1])}</{kind}>")
        elif kind == "p":
            out.append(f"<p>{e(block[1])}</p>")
        elif kind == "note":
            out.append(f"<p class='note'>{e(block[1])}</p>")
        elif kind == "kv":
            rows = "".join(f"<tr><th>{e(k)}</th><td>{e(_d(v))}</td></tr>" for k, v in block[1])
            out.append(f"<table class='kv'>{rows}</table>")
        elif kind == "table":
            head = "".join(f"<th>{e(h)}</th>" for h in block[1])
            body = "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in row) + "</tr>"
                           for row in block[2])
            out.append(f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")
    out.append("</body></html>")
    return "".join(out)


def to_docx(blocks, title) -> bytes:
    from docx import Document as Docx
    from docx.enum.section import WD_ORIENT
    from docx.shared import Cm, Pt, RGBColor

    doc = Docx()
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, side, Cm(1.8))
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10)
    doc.core_properties.title = title

    def add_table(headers, rows, kv=False):
        t = doc.add_table(rows=0, cols=len(headers) if not kv else 2)
        t.style = "Table Grid"
        if not kv:
            cells = t.add_row().cells
            for i, h in enumerate(headers):
                cells[i].text = h
                for r in cells[i].paragraphs[0].runs:
                    r.bold = True
        for row in rows:
            cells = t.add_row().cells
            for i, v in enumerate(row):
                cells[i].text = _d(v)
                if kv and i == 0:
                    for r in cells[i].paragraphs[0].runs:
                        r.bold = True
        for row in t.rows:
            for c in row.cells:
                for para in c.paragraphs:
                    for r in para.runs:
                        r.font.size = Pt(8.5)
        doc.add_paragraph()

    first_h1 = True
    for block in blocks:
        kind = block[0]
        if kind == "title":
            doc.add_heading(block[1], level=0)
        elif kind == "h1":
            if not first_h1:
                doc.add_page_break()
            first_h1 = False
            doc.add_heading(block[1], level=1)
        elif kind == "h2":
            doc.add_heading(block[1], level=2)
        elif kind == "p":
            doc.add_paragraph(block[1])
        elif kind == "note":
            para = doc.add_paragraph()
            run = para.add_run(block[1])
            run.italic = True
            run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
        elif kind == "kv":
            add_table(["", ""], block[1], kv=True)
        elif kind == "table":
            add_table(block[1], block[2])
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _csv(headers, rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for r in rows:
        w.writerow([_d(c) if not isinstance(c, str) else c for c in r])
    return buf.getvalue().encode("utf-8-sig")


def device_audit_events(device, data):
    refs = [device.code] + [h.ref for h in data["hazards"]]
    refs += [f"{h.ref}/RC-{c.pk}" for h in data["hazards"] for c in h.controls.all()]
    for versions in data["sections"].values():
        for v in versions:
            refs += [v.document.number, v.audit_ref]
    refs += [b.label for b in data["builds"]]
    return AuditEvent.objects.filter(Q(record__device=device) | Q(object_ref__in=refs)) \
        .select_related("record").order_by("id")


def preview_html(device: Device, user) -> str:
    data = gather(device)
    checks = completeness_checks(device, data)
    meta = {"label": "PREVIEW", "generated_at": timezone.now(),
            "generated_by": user.get_full_name() or user.get_username()}
    return to_html(build_outline(device, data, checks, meta),
                   f"Technical file preview – {device.name}",
                   banner="Preview only – not a controlled build. Generate a technical file to "
                          "create a frozen, checksummed package.")


# ---------------------------------------------------------------------------
# Package generation and approval
# ---------------------------------------------------------------------------

def generate_technical_file(device: Device, user) -> TechnicalFileBuild:
    from django.core.files.base import ContentFile

    from .services import TransitionError, _device_error
    if _device_error(user, device):
        raise TransitionError(_device_error(user, device))

    with transaction.atomic():
        n = TechnicalFileBuild.objects.select_for_update().filter(device=device).count()
        label = f"TF-{device.code}-{n + 1:03d}"
        now = timezone.now()
        data = gather(device)
        checks = completeness_checks(device, data)
        meta = {"label": label, "generated_at": now,
                "generated_by": user.get_full_name() or user.get_username()}
        blocks = build_outline(device, data, checks, meta)
        title = f"{label} Technical Documentation – {device.name}"

        files = {}  # path -> bytes
        files["00_technical_file.html"] = to_html(blocks, title).encode("utf-8")
        files["00_technical_file.docx"] = to_docx(blocks, title)
        files["registers/risk_register.csv"] = _csv(
            ["ref", "title", "hazard", "cause", "hazardous_situation", "harm", "software_item",
             "severity_initial", "probability_initial", "severity_residual",
             "probability_residual", "status", "benefit_risk_rationale"],
            [[h.ref, h.title, h.hazard, h.cause, h.hazardous_situation, h.harm, h.software_item,
              h.severity_initial, h.probability_initial, h.severity_residual,
              h.probability_residual, h.status, h.benefit_risk_rationale]
             for h in data["hazards"]])
        files["registers/risk_controls.csv"] = _csv(
            ["hazard", "control", "type", "implemented_by", "verified", "evidence"],
            [[h.ref, c.description, c.control_type,
              c.implemented_by.ref if c.implemented_by else "", c.verified,
              c.verification_evidence] for h in data["hazards"] for c in h.controls.all()])
        files["registers/soup_list.csv"] = _csv(
            ["name", "version", "supplier", "software_item", "safety_class", "licence",
             "last_anomaly_review", "known_anomalies"],
            [[s.name, s.version, s.supplier, s.software_item, s.safety_class, s.licence,
              s.last_anomaly_review, s.known_anomalies] for s in data["soup"]])
        files["registers/quality_records.csv"] = _csv(
            ["ref", "type", "title", "status", "severity", "patient_safety_impact",
             "software_version", "fix_version", "created_at", "closed_at"],
            [[r.ref, r.type_label, r.title, r.status, r.severity, r.patient_safety_impact,
              r.software_version, r.fix_version, r.created_at, r.closed_at]
             for r in Record.objects.filter(device=device).order_by("ref")])
        files["registers/audit_trail.csv"] = _csv(
            ["id", "timestamp", "subject", "actor", "action", "changes", "comment", "hash"],
            [[e.id, e.timestamp.isoformat(), e.subject, e.actor_name, e.action,
              json.dumps(e.changes), e.comment, e.hash]
             for e in device_audit_events(device, data)])

        for versions in data["sections"].values():
            for v in versions:
                if v.file and v.verify():
                    with v.file.open("rb") as fh:
                        files[_doc_path(v)] = fh.read()

        manifest = {
            "technical_file": label,
            "device": {"name": device.name, "code": device.code,
                       "software_version": device.current_version,
                       "classification": device.classification,
                       "basic_udi_di": device.basic_udi_di},
            "generated_at": now.isoformat(),
            "generated_by": meta["generated_by"],
            "files": [{"path": path, "sha256": hashlib.sha256(content).hexdigest(),
                       "size": len(content)} for path, content in sorted(files.items())],
            "completeness_checks": checks,
        }
        files["manifest.json"] = json.dumps(manifest, indent=2).encode("utf-8")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for path, content in sorted(files.items()):
                z.writestr(f"{label}/{path}", content)
        payload = ContentFile(buf.getvalue(), name=f"{label}.zip")

        build = TechnicalFileBuild(
            device=device, label=label, software_version=device.current_version,
            sha256=sha256_of(payload), size=payload.size, checks=checks,
            error_count=sum(1 for c in checks if c["level"] == "error"),
            warning_count=sum(1 for c in checks if c["level"] == "warning"),
            generated_by=user)
        build.package.save(os.path.basename(payload.name), payload, save=False)
        build.save(_actor=user)
    return build


def approve_technical_file(build: TechnicalFileBuild, user, secret: str, comment: str = ""):
    from .services import (TransitionError, _check_secret, _independent, _role_error, require,
                           sign)
    from .services import _device_error
    errors = _device_error(user, build.device) + _role_error(user, [wf.QA], build.device)
    require(errors, build.status == "generated", "Only newly generated builds can be approved.")
    require(errors, build.error_count == 0,
            f"{build.error_count} completeness error(s) must be resolved; generate a new build "
            "after fixing them.")
    require(errors, not build.warning_count or bool(comment.strip()),
            f"{build.warning_count} warning(s): record why they are acceptable in the comment.")
    _independent(errors, user, build.generated_by)
    require(errors, build.verify(), "Package integrity check failed: the stored file changed.")
    _check_secret(errors, user, secret)
    if errors:
        raise TransitionError(errors)
    with transaction.atomic():
        sign(build, user, secret, "Technical file approval", from_status="generated",
             to_status="approved", comment=comment)
        for old in build.device.technical_files.filter(status="approved"):
            old.status = "superseded"
            old.save(_via_workflow=True, _actor=user, _comment=f"Superseded by {build.label}")
        build.status = "approved"
        build.approved_at = timezone.now()
        build.save(_via_workflow=True, _actor=user, _comment=comment)
    return build
