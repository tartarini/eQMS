"""In-app help: topics, the help link for every page, and the help text for every form field.

One source for both places help appears:
  * the "?" icon beside each form field (``templatetags/qms_help.py``), and
  * the "Fields" reference at the end of each help topic (``render_topic``).

Topic pages are Markdown files in ``qms/help/``, shipped with each release so the help always
matches the version in use. ``qms.test_help`` fails if a page, form field or topic lacks help.
"""
import re
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.urls import reverse
from django.utils.html import escape

HELP_DIR = Path(__file__).resolve().parent / "help"

# (slug, title, one-line summary), in reading order.
TOPICS = [
    ("getting-started", "Getting started",
     "Signing in, roles, signing PIN, connected accounts, the dashboard and emails."),
    ("devices", "Devices, teams and technical files",
     "Adding devices, software items, device teams, and generating the technical file."),
    ("records", "Quality records",
     "Problem Reports, Complaints, Incidents, CAPAs, Change Requests and PMS activities."),
    ("documents", "Documents", "Controlled documents, versions, approval and periodic review."),
    ("training", "Training", "Your training, training requirements and the training matrix."),
    ("risk", "Risk management", "Hazards, risk controls, scoring and risk acceptance."),
    ("suppliers", "Suppliers and SOUP", "Supplier evaluation and the SOUP list."),
    ("audit", "Audit trail", "What is recorded, the integrity check and exporting."),
    ("troubleshooting", "Rules and troubleshooting", "Rules everyone follows, and fixes."),
]
TOPIC_TITLES = {slug: title for slug, title, _ in TOPICS}

# Help for each page, by URL name: (topic, section anchor). Anchors are the heading ids in the
# topic (heading text, lower case, spaces as hyphens). Every URL name must be listed here.
PAGE_HELP = {
    # account and sign-in
    "login": ("getting-started", "signing-in"),
    "logout": ("getting-started", "signing-in"),
    "socialaccount_connections": ("getting-started", "connected-accounts"),
    "signing_pin": ("getting-started", "signing-pin"),
    "dashboard": ("getting-started", "the-dashboard"),
    # records
    "record_list": ("records", ""),
    "record_create": ("records", "working-on-a-record"),
    "record_detail": ("records", "working-on-a-record"),
    "record_edit": ("records", "working-on-a-record"),
    "record_transition": ("records", "working-on-a-record"),
    "record_link": ("records", "linking-records"),
    "record_unlink": ("records", "linking-records"),
    "record_attach": ("records", "attachments"),
    "record_audit_export": ("audit", "exporting"),
    "attachment_download": ("records", "attachments"),
    # documents and training
    "document_list": ("documents", ""),
    "document_create": ("documents", "create-or-revise-a-document"),
    "document_detail": ("documents", ""),
    "document_edit": ("documents", "create-or-revise-a-document"),
    "version_create": ("documents", "create-or-revise-a-document"),
    "version_edit": ("documents", "create-or-revise-a-document"),
    "version_download": ("documents", ""),
    "version_action": ("documents", "create-or-revise-a-document"),
    "document_obsolete": ("documents", "periodic-review-and-withdrawal"),
    "requirement_add": ("training", "for-qa"),
    "requirement_remove": ("training", "for-qa"),
    "my_training": ("training", ""),
    "training_complete": ("training", ""),
    "training_matrix": ("training", "for-qa"),
    # risk
    "hazard_list": ("risk", ""),
    "hazard_create": ("risk", "add-and-control-a-hazard"),
    "hazard_detail": ("risk", ""),
    "hazard_edit": ("risk", "add-and-control-a-hazard"),
    "hazard_action": ("risk", "accept-the-residual-risk"),
    "control_add": ("risk", "add-and-control-a-hazard"),
    "control_edit": ("risk", "add-and-control-a-hazard"),
    # suppliers and SOUP
    "supplier_list": ("suppliers", ""),
    "supplier_create": ("suppliers", "suppliers"),
    "supplier_detail": ("suppliers", "suppliers"),
    "supplier_edit": ("suppliers", "suppliers"),
    "supplier_evaluate": ("suppliers", "evaluate-a-supplier"),
    "soup_create": ("suppliers", "the-soup-list"),
    "soup_edit": ("suppliers", "the-soup-list"),
    # devices
    "device_list": ("devices", ""),
    "device_create": ("devices", "add-a-device"),
    "device_detail": ("devices", ""),
    "device_edit": ("devices", "add-a-device"),
    "set_device": ("devices", "choose-a-device"),
    "team_add": ("devices", "device-teams"),
    "team_remove": ("devices", "device-teams"),
    "techfile_preview": ("devices", "generate-and-approve-a-technical-file"),
    "techfile_generate": ("devices", "generate-and-approve-a-technical-file"),
    "techfile_download": ("devices", "generate-and-approve-a-technical-file"),
    "techfile_approve": ("devices", "generate-and-approve-a-technical-file"),
    # audit
    "audit_log": ("audit", ""),
    "audit_export": ("audit", "exporting"),
    # help itself
    "help_index": ("", ""),
    "help_topic": ("", ""),
}

# Field help, grouped. Each group: topic it belongs to, title of its reference table, and
# {field: (label, help)}. Help may use {placeholders} from help_vars().
FIELD_HELP = {
    "record": ("records", "Quality record fields", {
        "device": ("Device", "The medical device this record is about. You can only choose "
                   "devices whose team you are on. It decides who can see the record, who is "
                   "emailed, and which hazards and software items can be linked."),
        "title": ("Title", "A short summary someone can understand in a list, for example "
                  "\"Upload fails for photos over 10 MB\"."),
        "description": ("Description", "What happened or what is proposed, in enough detail for "
                        "someone else to act on. Never enter patient or participant data: no "
                        "names, NHS or hospital numbers, identifiable images or recordings. Use "
                        "anonymised site or study IDs."),
        "owner": ("Owner", "The person responsible for moving the record forward. They are "
                  "emailed when assigned. Leave blank until someone takes it on."),
        "source": ("Source", "Where the report came from. Used to trend complaints and "
                   "problems in post-market surveillance."),
        "severity": ("Severity", "Impact on the user or patient if the problem occurs: "
                     "Critical (could cause serious harm or stops clinical use), Major (wrong or "
                     "missing output with a workaround), Minor (inconvenience), Cosmetic. Needed "
                     "before a Problem Report moves to risk assessment."),
        "patient_safety_impact": ("Patient safety impact", "Could this lead to harm to a "
                                  "patient? Choose Unknown until it has been assessed. Open items "
                                  "marked Yes are highlighted on the dashboard."),
        "software_version": ("Software version", "The version where the problem was seen, "
                             "exactly as shown in the product, for example 2.3.1."),
        "software_item": ("Software item", "The part of the device's software involved. Choose "
                          "one of the device's software items (listed on the device page); the "
                          "box suggests them as you type. If the device has no list yet, enter "
                          "the item's name."),
        "soup_involved": ("SOUP involved", "The third-party library, model or service involved, "
                          "with its version, if any (for example \"OpenCV 4.10.0\"). It should be "
                          "on the SOUP list."),
        "hazards": ("Hazards", "Entries in the risk register that this record affects. Only "
                    "hazards of the same device can be linked. Hold Ctrl (Cmd on a Mac) to "
                    "choose several."),
        "risk_file_updated": ("Risk file updated", "Whether the risk file (hazards and risk "
                              "controls) has been updated for this record: Yes, Not needed, or "
                              "Pending. Pending blocks starting a fix, approving a change and "
                              "closing a CAPA."),
        "verification_evidence": ("Verification evidence", "Where the proof is that the fix or "
                                  "action works: a link to the test run, pull request or report, "
                                  "or a document number."),
        "resolution": ("Resolution / outcome", "What was done and the result. Needed to close "
                       "Incidents and CAPAs."),
        "date_aware": ("Date aware", "The day anyone in the organisation first became aware of "
                       "it. It starts the reporting clock, so record it the same day and never "
                       "use the date you logged it if that was later. It cannot be in the "
                       "future."),
        "investigation_summary": ("Investigation summary / findings", "What you checked, what "
                                  "you found and the conclusion. For PMS activities, what was "
                                  "reviewed and any records raised."),
        "reportable": ("Reportable to MHRA", "The reportability decision, made by QA or the "
                       "Clinical Safety Officer. Yes means an Incident must be created and "
                       "linked (\"escalated to\") before the complaint can close."),
        "reportability_rationale": ("Reportability rationale", "Why it is or is not reportable, "
                                    "referring to the vigilance criteria you applied."),
        "deadline_category": ("Deadline category", "Sets the reporting deadline counted from "
                              "the date aware: {deadlines}. The deadlines are a reminder only; "
                              "always check current MHRA guidance."),
        "mhra_reference": ("MHRA reference", "The reference the MHRA gave your report. Needed "
                           "to record the report as submitted."),
        "root_cause": ("Root cause", "The underlying cause, not the symptom, and how it was "
                       "found (for example 5 whys or a fishbone)."),
        "effectiveness_due": ("Effectiveness check due", "When to check that the actions "
                              "worked, usually some months after implementation."),
        "impact_analysis": ("Impact analysis", "The effect of the change on risk, requirements, "
                            "design, tests and regression scope, and on other devices that share "
                            "the code. Needed before QA approves the change."),
        "fix_version": ("Fix version", "The released software version that contains the "
                        "change. Needed to close a Change Request."),
        "due_date": ("Due date", "When the PMS activity must be completed. Set by the PMS "
                     "schedule."),
        "period_start": ("Period start", "First day of the period this PMS activity reviews."),
        "period_end": ("Period end", "Last day of the period this PMS activity reviews."),
    }),
    "sign": ("getting-started", "Signature fields", {
        "comment": ("Comment", "Why you are taking this step. Required when rejecting or sending "
                    "something back, and for accepting technical-file warnings."),
        "password": ("Password or signing PIN", "Re-enter your password, or your signing PIN if "
                     "you have set one, to sign. Your signature records your name, the time, "
                     "its meaning and a fingerprint of exactly what you signed, and cannot be "
                     "changed."),
    }),
    "link": ("records", "Link fields", {
        "link_type": ("Link type", "How this record relates to the other one, read as \"this "
                      "record … the other record\". For example a Problem Report \"is fixed by\" "
                      "a Change Request; a Complaint is \"escalated to\" an Incident."),
        "target_ref": ("Record reference", "The other record's reference, for example "
                       "CR-0003. It must belong to a device whose team you are on."),
    }),
    "attachment": ("records", "Attachment fields", {
        "file": ("File", "Evidence such as a log, test report or screenshot. Allowed types: "
                 "{extensions}; up to {max_mb} MB. Files cannot be changed or deleted after "
                 "upload."),
        "description": ("Description", "What the file is and why it is attached."),
        "confirm_no_participant_data": ("No patient data", "Tick to confirm the file has no "
                                        "patient or participant data. Remove or blur names, "
                                        "numbers and faces before uploading."),
    }),
    "document": ("documents", "Document fields", {
        "title": ("Title", "The document's name as it appears on the document itself."),
        "doc_type": ("Type", "The kind of document. It sets the number prefix (for example "
                     "SOP-001) and cannot be changed later."),
        "device": ("Device", "Leave blank for QMS-wide documents, such as SOPs and policies, "
                   "that apply to every device. Choose a device for documents about one device; "
                   "only its team will see them."),
        "tech_file_section": ("Technical file section", "Where the effective version goes in "
                              "the device's technical file. Choose \"Not part of the technical "
                              "file\" for procedures and records."),
        "description": ("Description", "What the document covers and who it is for."),
        "owner": ("Owner", "The person responsible for keeping the document up to date."),
        "review_period_months": ("Review period (months)", "How often the effective version "
                                 "must be reviewed. Reviews due soon appear on the dashboard."),
    }),
    "documentversion": ("documents", "Version fields", {
        "version": ("Version", "The version number, for example 2.0. The next major version is "
                    "suggested."),
        "change_summary": ("Change summary", "What changed since the previous version and why. "
                           "Reviewers and trainees read this first."),
        "file": ("File", "The document file. It is frozen when you submit for review; to "
                 "change it after that, QA returns the version to you. Allowed types: "
                 "{extensions}; up to {max_mb} MB."),
        "change_request": ("Change request", "The Change Request that authorised this revision, "
                           "if there is one."),
    }),
    "training": ("training", "Training requirement fields", {
        "group": ("Role that must be trained", "Everyone with this role (on the document's "
                  "device team, for device documents) is assigned the effective version now and "
                  "each new version, with {training_days} days to complete it."),
    }),
    "hazard": ("risk", "Hazard fields", {
        "device": ("Device", "The device this hazard belongs to. Each device has its own risk "
                   "file."),
        "title": ("Title", "A short name for the hazard, for example \"Missed urgent "
                  "referral\"."),
        "hazard": ("Hazard", "The potential source of harm, for example \"the model returns a "
                   "false negative\"."),
        "cause": ("Sequence of events / cause", "How the hazard could arise, step by step, "
                  "including software causes."),
        "hazardous_situation": ("Hazardous situation", "The circumstance in which someone is "
                                "exposed to the hazard, for example \"the clinician receives a "
                                "low-risk result for a high-risk patient\"."),
        "harm": ("Harm", "The injury or damage to health that could result, for example "
                 "\"delayed diagnosis and treatment\"."),
        "software_item": ("Software item", "The part of the device's software that contributes "
                          "to the hazard. Choose one of the device's software items."),
        "owner": ("Owner", "The person responsible for controlling this risk."),
        "severity_initial": ("Severity (before controls)", "How bad the harm would be: "
                             "1 Negligible to 5 Catastrophic."),
        "probability_initial": ("Probability (before controls)", "How likely the harm is "
                                "before any risk controls: 1 Improbable to 5 Frequent."),
        "severity_residual": ("Severity (residual)", "How bad the harm would be with all risk "
                              "controls in place. Needed before the risk can be accepted."),
        "probability_residual": ("Probability (residual)", "How likely the harm is with all "
                                 "risk controls in place. Needed before the risk can be "
                                 "accepted."),
        "benefit_risk_rationale": ("Benefit-risk rationale", "Why the medical benefit outweighs "
                                   "a residual risk scored above {acceptable_max} (not "
                                   "acceptable by the matrix). Required before such a risk can "
                                   "be accepted."),
    }),
    "riskcontrol": ("risk", "Risk control fields", {
        "description": ("Description", "What the control does to reduce the risk."),
        "control_type": ("Control type", "In order of preference (ISO 14971): inherent safety "
                         "by design, protective measures in the device, then information for "
                         "safety such as warnings or training."),
        "implemented_by": ("Implemented by", "The Change Request that implements the control. "
                           "Only this device's records are offered."),
        "verification_evidence": ("Verification evidence", "The test, review or report showing "
                                  "the control works. Required before it can be marked "
                                  "verified."),
        "verified": ("Verified", "Tick once the evidence shows the control is implemented and "
                     "effective. Every control must be verified before the risk is accepted."),
    }),
    "supplier": ("suppliers", "Supplier fields", {
        "name": ("Name", "The supplier's legal or trading name."),
        "category": ("Category", "The kind of product or service supplied."),
        "criticality": ("Criticality", "How much the supplier affects device safety and "
                        "performance. High-criticality suppliers need the closest control."),
        "scope": ("Scope", "What they supply and how it is used, including which devices rely "
                  "on it."),
        "contact": ("Contact", "Who to contact at the supplier, for example an account manager "
                    "or support address."),
        "evaluation_interval_months": ("Evaluation interval (months)", "How often to "
                                       "re-evaluate the supplier. Overdue evaluations appear on "
                                       "the dashboard."),
        "notes": ("Notes", "Anything else worth knowing, such as contract or certificate "
                  "dates."),
    }),
    "suppliereval": ("suppliers", "Supplier evaluation fields", {
        "outcome": ("Outcome", "Approved, Conditionally approved (state the conditions in the "
                    "notes) or Disqualified. Only approved suppliers may be relied on."),
        "notes": ("Notes", "The evidence reviewed (certificates, audits, questionnaires, "
                  "performance) and your conclusion."),
        "password": ("Password or signing PIN", "Re-enter your password or signing PIN to sign "
                     "the evaluation."),
    }),
    "soupitem": ("suppliers", "SOUP item fields", {
        "name": ("Name", "The library, model or component name as published."),
        "version": ("Version", "The exact version in use, for example 4.10.0, not a range."),
        "supplier": ("Supplier", "The supplier, if it is on the supplier list."),
        "devices": ("Devices", "The devices whose software includes this item."),
        "software_item": ("Software item", "Where it is used in the device's software. Choose "
                          "one of the selected devices' software items."),
        "purpose": ("Purpose", "The functional and performance requirements it meets (IEC "
                    "62304 §5.3.3)."),
        "licence": ("Licence", "Its licence, for example MIT or Apache-2.0."),
        "safety_class": ("Software safety class", "The IEC 62304 class of the software item "
                         "that uses it."),
        "known_anomalies": ("Known anomalies", "Published bugs and vulnerabilities you reviewed "
                            "and their impact on the device (IEC 62304 §7.1.3)."),
        "last_anomaly_review": ("Last anomaly review", "When you last checked for new "
                                "anomalies. Items not reviewed for {soup_days} days are "
                                "flagged."),
        "active": ("Active", "Untick when the item is no longer used. It stays on record."),
    }),
    "team": ("devices", "Team fields", {
        "user": ("Person", "Someone with a QMS role who is not yet on this team. People can be "
                 "on several teams."),
        "note": ("Responsibility", "Optional: their role on this device, for example "
                 "\"Clinical safety\" or \"Lead developer\"."),
    }),
    "device": ("devices", "Device fields", {
        "name": ("Name", "The device's name as on its label."),
        "code": ("Code", "A short unique code shown in lists, emails and technical file names, "
                 "for example HRT1. Letters and numbers only; it cannot easily be changed."),
        "owner": ("Owner", "The person accountable for the device's quality records."),
        "current_version": ("Current software version", "The version currently released or "
                            "under investigation."),
        "regulatory_status": ("Regulatory status", "Where the device is in its life cycle. "
                              "\"On the market\" makes the technical file check stricter."),
        "markets": ("Markets", "Where it is or will be placed on the market, for example "
                    "\"UK (UKCA), EU (CE)\"."),
        "description": ("Description and principle of operation", "What the device is and how "
                        "it works, for the technical file."),
        "intended_purpose": ("Intended purpose", "What the device is for, exactly as in the "
                             "instructions for use."),
        "intended_users": ("Intended users", "Who operates the device and the training they "
                           "need."),
        "patient_population": ("Intended patient population", "Who the device is used on or "
                                "for."),
        "contraindications": ("Contraindications and limitations", "When it must not be used, "
                              "and its known limitations."),
        "classification": ("Classification", "The device class under the regulations that "
                           "apply."),
        "classification_rule": ("Classification rationale", "The classification rule applied "
                                "and why, for example \"MDR Annex VIII Rule 11\"."),
        "software_safety_class": ("IEC 62304 software safety class", "A, B or C, from the "
                                  "worst harm a software failure could contribute to."),
        "software_items": ("Software items", "The main parts of the device's software "
                           "(IEC 62304 architecture), one per line, for example \"Mobile app\", "
                           "\"Analysis engine\", \"Clinician portal\". Records, hazards and SOUP "
                           "items for this device choose from this list."),
        "basic_udi_di": ("Basic UDI-DI", "The device's Basic UDI-DI, once assigned."),
        "manufacturer": ("Legal manufacturer", "Name and address of the legal manufacturer."),
        "uk_responsible_person": ("UK Responsible Person / authorised rep.", "Name and address, "
                                  "if the manufacturer is outside the UK, or the EU authorised "
                                  "representative for the EU."),
        "approved_body": ("Approved / notified body", "The conformity assessment body, if "
                          "one is involved."),
        "standards_applied": ("Standards applied", "Harmonised or recognised standards applied, "
                              "one per line, with their versions."),
        "active": ("Active", "Untick when the device is retired. Its records are kept."),
    }),
    "signingpin": ("getting-started", "Signing PIN fields", {
        "current_password": ("Current password", "Your SAMD_QMS password, to confirm it is "
                             "you."),
        "pin": ("New signing PIN", "At least 6 characters, used only for signing. Don't reuse a "
                "password, and never share it: your signature means you personally approved."),
        "pin_confirm": ("Repeat signing PIN", "Type the same PIN again."),
    }),
    "connections": ("getting-started", "Connected account fields", {
        "account": ("Connected account", "Select an account and click Remove selected to stop "
                    "signing in with it. Make sure you can still sign in another way first."),
    }),
    "recordfilter": ("records", "Record list filters", {
        "type": ("Type", "Show only one kind of record."),
        "status": ("Status", "Show only records in this status. \"Open\" means anything not "
                   "yet closed, rejected or done."),
        "q": ("Search", "Matches the reference (for example PR-0004), title and description."),
    }),
    "auditfilter": ("audit", "Audit trail filters", {
        "kind": ("Show", "All entries, only security events (sign-ins, failed sign-ins, role "
                 "and team changes, connected accounts), or only signatures."),
        "q": ("Search", "Matches an item's reference or a person's username."),
    }),
    "login": ("getting-started", "Sign-in fields", {
        "username": ("Username", "Your SAMD_QMS username, from your administrator."),
        "password": ("Password", "Your SAMD_QMS password. If you use single sign-on, choose "
                     "\"Continue with…\" instead."),
    }),
}

# Form class name -> group, for forms that are not plain model forms or share a model.
FORM_GROUPS = {
    "SignForm": "sign", "LinkForm": "link", "AttachmentForm": "attachment",
    "VersionForm": "documentversion", "TrainingRequirementForm": "training",
    "SupplierEvaluationForm": "suppliereval", "TeamMemberForm": "team",
    "SigningPinForm": "signingpin", "AuthenticationForm": "login",
}


def help_vars() -> dict:
    deadlines = "; ".join(f"{v['label']}, {v['days']} days"
                          for v in settings.QMS_VIGILANCE_DEADLINES.values())
    return {
        "deadlines": deadlines,
        "extensions": ", ".join(e.lstrip(".") for e in settings.QMS_ATTACHMENT_EXTENSIONS),
        "max_mb": settings.QMS_ATTACHMENT_MAX_MB,
        "training_days": settings.QMS_TRAINING_DUE_DAYS,
        "soup_days": settings.QMS_SOUP_REVIEW_DAYS,
        "acceptable_max": settings.QMS_RISK_ACCEPTABLE_MAX,
    }


def group_for_form(form) -> str:
    name = type(form).__name__
    if name in FORM_GROUPS:
        return FORM_GROUPS[name]
    meta = getattr(form, "_meta", None)
    model = getattr(meta, "model", None)
    return model._meta.model_name if model is not None else ""


def field_anchor(group: str, field: str) -> str:
    return f"field-{group}-{field}".replace("_", "-")


def help_url(topic: str, anchor: str = "") -> str:
    if not topic:
        return reverse("qms:help_index")
    url = reverse("qms:help_topic", args=[topic])
    return f"{url}#{anchor}" if anchor else url


def field_help(form, field_name: str):
    """(label, text, url) for a field of a form, or None if no help is registered."""
    return group_field_help(group_for_form(form), field_name)


def group_field_help(group: str, field_name: str):
    """(label, text, url) for a field in a help group, or None if no help is registered."""
    entry = FIELD_HELP.get(group)
    if not entry or field_name not in entry[2]:
        return None
    topic, _title, fields = entry
    label, text = fields[field_name]
    return label, text.format(**help_vars()), help_url(topic, field_anchor(group, field_name))


def page_help_url(url_name: str):
    if url_name not in PAGE_HELP:
        return None
    return help_url(*PAGE_HELP[url_name])


# --- topic pages ------------------------------------------------------------------------

def _fields_reference(topic: str) -> str:
    """Markdown for every field group belonging to a topic."""
    out = []
    for group, (group_topic, title, fields) in FIELD_HELP.items():
        if group_topic != topic:
            continue
        out.append(f"### {title}\n")
        for name, (label, text) in fields.items():
            out.append(f'<div class="field-help" id="{field_anchor(group, name)}" markdown="1">\n'
                       f"**{escape(label)}**: {text.format(**help_vars())}\n</div>\n")
    return "\n".join(out)


@lru_cache(maxsize=None)
def _render(slug: str) -> tuple:
    import markdown
    source = (HELP_DIR / f"{slug}.md").read_text(encoding="utf-8")
    reference = _fields_reference(slug)
    if reference:
        source += "\n\n## Fields\n\nEvery field on this topic's forms, as shown by its ? icon.\n\n"
        source += reference
    md = markdown.Markdown(extensions=["tables", "toc", "md_in_html", "attr_list"],
                           extension_configs={"toc": {"permalink": False}})
    html = md.convert(source)
    return html, md.toc_tokens


def render_topic(slug: str) -> tuple:
    """(html, table of contents tokens) for a topic. Cached; topics change only on release."""
    if slug not in TOPIC_TITLES:
        raise KeyError(slug)
    if settings.DEBUG:
        _render.cache_clear()
    return _render(slug)


def topic_anchors(slug: str) -> set:
    def walk(tokens):
        for t in tokens:
            yield t["id"]
            yield from walk(t["children"])
    html, toc = render_topic(slug)
    ids = set(walk(toc))
    ids.update(re.findall(r'id="([^"]+)"', html))
    return ids
