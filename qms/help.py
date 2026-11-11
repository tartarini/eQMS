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
    "access_request": ("getting-started", "request-an-account"),
    "access_request_details": ("getting-started", "request-an-account"),
    "access_request_confirm": ("getting-started", "request-an-account"),
    "access_request_list": ("devices", "review-account-requests"),
    "access_request_approve": ("devices", "review-account-requests"),
    "access_request_decline": ("devices", "review-account-requests"),
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
    "device_list": ("devices", "choose-a-device"),
    "organisation": ("devices", "your-organisation-and-its-roles"),
    "organisation_edit": ("devices", "your-organisation-and-its-roles"),
    "device_create": ("devices", "add-a-device"),
    "device_detail": ("devices", ""),
    "device_tasks": ("devices", "my-tasks"),
    "gate_approve": ("devices", "my-tasks"),
    "device_edit": ("devices", "add-a-device"),
    "set_device": ("devices", "choose-a-device"),
    "people": ("devices", "people"),
    "team_add": ("devices", "device-teams"),
    "team_remove": ("devices", "device-teams"),
    "team_roles": ("devices", "roles-on-each-device"),
    "invitation_list": ("devices", "manage-invitations"),
    "invitation_create": ("devices", "invite-people"),
    "invitation_revoke": ("devices", "manage-invitations"),
    "invitation_resend": ("devices", "manage-invitations"),
    "invitation_accept": ("getting-started", "accept-an-invitation"),
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
        "audit_scope": ("Audit scope", "The clauses, processes, documents or areas being "
                        "audited, for example \"ISO 13485 7.4 purchasing, supplier SOUP "
                        "evaluations\"."),
        "auditee": ("Auditee", "The person responsible for the area being audited. The lead "
                    "auditor, who is the record's owner, cannot be the auditee: auditors do "
                    "not audit their own work."),
        "planned_date": ("Planned date", "The date the audit, management review or design "
                         "review is planned for. It is shown as due until the record is held."),
        "attendees": ("Attendees / participants", "Who took part, by name and role. For a design "
                      "review, the functions and specialists who reviewed the design."),
        "review_inputs": ("Review inputs", "What the review considered: feedback, complaints, "
                          "reports to regulators, audits, process and product monitoring, CAPA, "
                          "changes affecting the QMS, recommendations for improvement, and new or "
                          "revised regulatory requirements. Say what was considered for each."),
        "resource_needs": ("Resource needs", "Resources the review decided are needed, such as "
                           "people, training, tools or budget. Write \"None\" if there are none."),
        "nc_disposition": ("Disposition", "What happens to the nonconforming product: rework "
                           "(then verify), use as is under concession, scrap, or return to the "
                           "supplier. A concession needs QA approval and its justification."),
        "concession_justification": ("Concession justification", "Why the nonconforming "
                                     "product can be used or released, the risk to the user, and "
                                     "what was checked. Required before a concession is approved."),
        "design_element": ("Design element", "What this record is: a design input (requirements "
                           "the design must meet), a design output (the design itself and its "
                           "acceptance criteria), or a design review."),
        "acceptance_criteria": ("Acceptance criteria", "The measurable criteria the design must "
                                "meet, or the requirements it must satisfy. Output records must "
                                "contain or reference them."),
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
        "user": ("Person", "Someone who already has a SAMD_QMS account and isn't on this team "
                 "yet. To add someone new, use Invite people instead."),
        "roles": ("Roles on this device", "What they can do on this device only: Engineer, QA, "
                  "Clinical Safety Officer, and Device admin (invites people and manages this "
                  "team). Tick as many as apply; they can hold different roles on other "
                  "devices."),
        "note": ("Responsibility", "Optional: their responsibility on this device, for example "
                 "\"Clinical safety\" or \"Lead developer\"."),
    }),
    "teamroles": ("devices", "Change roles fields", {
        "roles": ("Roles on this device", "Tick the roles this person holds on this device. "
                  "Changes take effect immediately and are in the audit trail. You can't change "
                  "your own roles, and a device always keeps at least one Device admin or QA."),
        "note": ("Responsibility", "Optional: their responsibility on this device."),
    }),
    "invitation": ("devices", "Invitation fields", {
        "email": ("Email address", "Where the invitation is sent. Only an account with this "
                  "email address can accept it, so use the address the person signs in with "
                  "(for single sign-on, their work email)."),
        "roles": ("Roles on a device", "The roles to give them on that device. Leave a device "
                  "blank to leave them off its team. You can only grant roles on devices whose "
                  "team you manage."),
        "expires_in_days": ("Link expires after (days)", "How long the link works, from "
                            "today: {invite_days} days by default, at most {invite_max_days}. "
                            "After that, resend it."),
        "message": ("Message", "Optional note included in the email, for example why you're "
                    "inviting them. Don't include passwords or patient data."),
    }),
    "device": ("devices", "Device fields", {
        "name": ("Name", "The device's name as on its label."),
        "operator_roles": ("Our role for this device", "What your organisation is for this "
                           "device under the MDR: manufacturer, authorised representative, "
                           "importer or distributor (one or more). Only the roles in the "
                           "organisation profile are offered. Choosing Manufacturer or "
                           "Authorised representative fills that field below with the "
                           "organisation's name and address if it is empty."),
        "code": ("Code", "A short unique code shown in lists, emails and technical file names, "
                 "for example HRT1. Letters and numbers only; it cannot easily be changed."),
        "owner": ("Owner", "The person accountable for the device's quality records."),
        "current_version": ("Current software version", "The version currently released or "
                            "under investigation."),
        "development_route": ("Documentation route", "Greenfield if the device is still in development and its documentation starts now. Retrofit if it already exists and its documentation is reconstructed. The route sets which approver gates appear on My tasks."),
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
        "eu_classification": ("EU MDR class", "The class under the EU Medical Device "
                              "Regulation (EU) 2017/745, Annex VIII: I, IIa, IIb or III. Class I "
                              "devices that are sterile (Is), have a measuring function (Im) or "
                              "are reusable surgical instruments (Ir) need a notified body for "
                              "that aspect; software with a measuring function can be Im. In the "
                              "EU the manufacturer and notified body classify devices, not EMA. "
                              "Choose \"Not for the EU market\" if it isn't placed there."),
        "uk_classification": ("UK MDR 2002 class (UKCA)", "The class under the UK Medical "
                              "Devices Regulations 2002 (Annex IX as modified by Schedule 2A), "
                              "for the UKCA mark: Class I, IIa, IIb or III, the four classes the "
                              "MHRA sets out. Choose \"Not for the UK market\" if it isn't "
                              "placed there."),
        "us_classification": ("FDA class", "The FDA device class under 21 CFR Part 860: "
                              "Class I, II or III, as given by the device's classification "
                              "regulation and product code. Choose \"Not for the US market\" if "
                              "it isn't placed there."),
        "classification_rule": ("Classification rationale", "For each market, the rule applied "
                                "and why, for example \"EU and UK: MDR Annex VIII Rule 11 (Rule "
                                "11 of UK MDR 2002 Annex IX for the UK); FDA: the classification "
                                "regulation (21 CFR part 8xx) and product code\"."),
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
        "expected_lifetime_years": ("Expected lifetime (years)", "How long the device is "
                                    "expected to be in use. Closed records and withdrawn "
                                    "documents are kept at least this long, and never less "
                                    "than two years. Leave blank only until it is decided."),
        "active": ("Active", "Untick when the device is retired. Its records are kept."),
    }),
    "organisation": ("devices", "Organisation profile fields", {
        "name": ("Legal name", "The legal entity running this QMS, as registered."),
        "address": ("Registered address", "Its registered address, as it appears on labels "
                    "and the declaration of conformity."),
        "srn": ("EU Single Registration Number (SRN)", "The number EUDAMED issued when the "
                "organisation registered as an economic operator, for example "
                "GB-MF-000012345. Leave blank if not registered in the EU."),
        "uk_registration": ("MHRA registration number", "The organisation's MHRA device "
                            "registration number, for the UK market."),
        "roles": ("Economic operator roles", "Every role the organisation holds for at least "
                  "one device: manufacturer (places a device on the market under its own "
                  "name), authorised representative (acts in the EU for a manufacturer outside "
                  "it), importer (first places a non-EU device on the EU market) or "
                  "distributor (makes a device available further down the supply chain). A "
                  "role still set on a device can't be removed."),
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
    "captcha": ("getting-started", "Account request check", {
        "verify": ("I'm not a robot", "Tick the box and wait a moment: your browser does a short "
                   "calculation that is easy for one person but costly for programs sending "
                   "thousands of requests. Nothing is sent to anyone else and no cookie is "
                   "set."),
    }),
    "accessrequest": ("getting-started", "Account request fields", {
        "first_name": ("First name", "As you'd like it shown on records and signatures."),
        "last_name": ("Last name", "As you'd like it shown on records and signatures."),
        "email": ("Email address", "Your work address. QMS emails (assignments, reviews, "
                  "training) go here. If your sign-in provider didn't confirm it, we email you a "
                  "link to confirm it first."),
        "organisation": ("Organisation", "The company, university or NHS trust you work for."),
        "position": ("Job title or position", "For example \"Software engineer\" or "
                     "\"Clinical safety officer\"."),
        "devices": ("Devices or projects", "The device or project you're working on, as the "
                    "team knows it, so QA can add you to the right team."),
        "role": ("Role you need", "What you'll do: Engineer, QA or Clinical Safety Officer; an "
                 "auditor who only reads; or \"Not sure\". QA decides the roles you get."),
        "reason": ("What you'll use SAMD_QMS for", "A sentence or two, and who asked you to "
                   "join if anyone did. Don't include patient or participant data."),
        "agree": ("Confirmation", "Confirms the details are yours and correct. QA may contact "
                  "you to check them."),
    }),
    "accessapprove": ("devices", "Account approval fields", {
        "device": ("Device team", "A device whose team you manage. The person is added to it "
                   "and can then see that device's records."),
        "roles": ("Roles on this device", "The roles they get on that device. Give the least "
                  "they need; you can change roles later on the device's team."),
        "note": ("Note", "Optional: kept with the decision in the audit trail."),
    }),
    "accessdecline": ("devices", "Account decline fields", {
        "reason": ("Reason", "Emailed to the person and kept in the audit trail. Be brief and "
                   "factual, for example \"Not part of a device team here\"."),
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
    "TeamRolesForm": "teamroles", "InvitationForm": "invitation",
    "AccessRequestForm": "accessrequest",
    "AccessApproveForm": "accessapprove", "AccessDeclineForm": "accessdecline",
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
        "invite_days": settings.QMS_INVITATION_DAYS,
        "invite_max_days": settings.QMS_INVITATION_MAX_DAYS,
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
    """(label, text, url) for a field of a form, or None if no help is registered.
    Forms with generated field names (roles_3, roles_7) map them with ``help_field_name``."""
    name = getattr(form, "help_field_name", lambda n: n)(field_name)
    return group_field_help(group_for_form(form), name)


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
