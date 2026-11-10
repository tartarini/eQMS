"""
Workflow definitions for each QMS record type.

Each record type is a small state machine. A transition can require:
  - fields to be filled before it is allowed (``required``),
  - the acting user to be in one of a set of groups (``roles``),
  - an electronic signature with a stated meaning (``signature``),
  - a comment (``comment_required``), e.g. a rejection rationale,
  - extra checks (``checks``): callables returning an error message or None,
  - an independent signer (``independent``): the signer may not be the record's author.

Status can only change through ``qms.services.perform_transition``.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

# Group names used for role checks. Created by ``manage.py seed_qms``.
ENGINEER = "Engineer"
QA = "QA"
CLINICAL_SAFETY = "Clinical Safety Officer"
ANY_ROLE = (ENGINEER, QA, CLINICAL_SAFETY)  # working roles: they act on quality records
# Administrative role: invites people and manages a device's team; no approval powers.
DEVICE_ADMIN = "Device admin"
ROLES = ANY_ROLE + (DEVICE_ADMIN,)            # every role a person can hold on a device
TEAM_MANAGERS = (DEVICE_ADMIN, QA)            # may invite people and manage a device's team
# Not a working role: grants access to every device's data (e.g. head of quality, auditors).
ALL_DEVICES = "All-device access"

# Record types
PROBLEM_REPORT = "problem_report"
COMPLAINT = "complaint"
INCIDENT = "incident"
CAPA = "capa"
CHANGE_REQUEST = "change_request"
PMS_ACTIVITY = "pms_activity"
INTERNAL_AUDIT = "internal_audit"          # ISO 13485 8.2.4
MANAGEMENT_REVIEW = "management_review"    # ISO 13485 5.6
NONCONFORMANCE = "nonconformance"          # ISO 13485 8.3
DESIGN_CONTROL = "design_control"          # ISO 13485 7.3.3 to 7.3.5

RECORD_TYPES = [
    (PROBLEM_REPORT, "Problem Report"),
    (COMPLAINT, "Complaint"),
    (INCIDENT, "Incident"),
    (CAPA, "CAPA"),
    (CHANGE_REQUEST, "Change Request"),
    (PMS_ACTIVITY, "PMS Activity"),
    (INTERNAL_AUDIT, "Internal Audit"),
    (MANAGEMENT_REVIEW, "Management Review"),
    (NONCONFORMANCE, "Nonconforming Product"),
    (DESIGN_CONTROL, "Design Control"),
]

REF_PREFIX = {
    PROBLEM_REPORT: "PR",
    COMPLAINT: "CMP",
    INCIDENT: "INC",
    CAPA: "CAPA",
    CHANGE_REQUEST: "CR",
    PMS_ACTIVITY: "PMS",
    INTERNAL_AUDIT: "IA",
    MANAGEMENT_REVIEW: "MR",
    NONCONFORMANCE: "NC",
    DESIGN_CONTROL: "DES",
}

# Dispositions of nonconforming product (ISO 13485 8.3.2). "Pending" is not a disposition.
NC_DISPOSITIONS = [
    ("rework", "Rework (then verify)"),
    ("use_as_is_concession", "Use as is under concession"),
    ("scrap", "Scrap / destroy"),
    ("return_to_supplier", "Return to supplier"),
]

# What a design control record is (ISO 13485 7.3.3 inputs, 7.3.4 outputs, 7.3.5 reviews).
DESIGN_ELEMENTS = [
    ("input", "Design input"),
    ("output", "Design output"),
    ("review", "Design review"),
]

# Which record fields are shown/editable for each type (besides title/description/owner).
TYPE_FIELDS = {
    PROBLEM_REPORT: [
        "source", "severity", "patient_safety_impact", "software_version", "software_item",
        "soup_involved", "hazards", "risk_file_updated", "verification_evidence", "resolution",
    ],
    COMPLAINT: [
        "source", "date_aware", "software_version", "severity", "patient_safety_impact",
        "investigation_summary", "reportable", "reportability_rationale",
    ],
    INCIDENT: [
        "date_aware", "deadline_category", "software_version", "severity", "patient_safety_impact",
        "hazards", "mhra_reference", "investigation_summary", "resolution",
    ],
    CAPA: [
        "patient_safety_impact", "hazards", "root_cause", "risk_file_updated",
        "verification_evidence", "effectiveness_due", "resolution",
    ],
    CHANGE_REQUEST: [
        "software_item", "soup_involved", "hazards", "impact_analysis", "risk_file_updated",
        "verification_evidence", "fix_version",
    ],
    PMS_ACTIVITY: ["due_date", "period_start", "period_end", "investigation_summary", "resolution"],
    INTERNAL_AUDIT: [
        "audit_scope", "auditee", "planned_date", "investigation_summary", "verification_evidence",
        "resolution",
    ],
    MANAGEMENT_REVIEW: [
        "planned_date", "attendees", "review_inputs", "resolution", "resource_needs",
    ],
    NONCONFORMANCE: [
        "software_version", "software_item", "risk_file_updated", "investigation_summary",
        "root_cause", "nc_disposition", "concession_justification", "verification_evidence",
        "resolution",
    ],
    DESIGN_CONTROL: [
        "design_element", "software_item", "acceptance_criteria", "planned_date", "attendees",
        "investigation_summary",
    ],
}

# Statuses in which a record is locked against further edits.
TERMINAL_STATES = {"closed", "rejected", "done"}


@dataclass(frozen=True)
class Transition:
    name: str
    label: str
    sources: tuple
    target: str
    roles: tuple = ANY_ROLE
    required: tuple = ()
    signature: Optional[str] = None  # meaning of the signature, e.g. "Approval"
    comment_required: bool = False
    independent: bool = False
    checks: tuple = field(default_factory=tuple)


# --- extra checks -----------------------------------------------------------

def _has_link(link_type: str, target_type: Optional[str] = None, label: str = "") -> Callable:
    def check(record):
        links = record.outgoing_links.filter(link_type=link_type)
        if target_type:
            links = links.filter(target__record_type=target_type)
        if not links.exists():
            return f"Needs a '{label or link_type}' link before this step."
        return None
    return check


def _auditor_independent(record):
    """ISO 13485 8.2.4: auditors shall not audit their own work."""
    if record.owner_id and record.owner_id == record.auditee_id:
        return "The lead auditor cannot be the auditee: auditors do not audit their own work."
    return None


def _concession_justified(record):
    """ISO 13485 8.3.2: a concession needs justification, approval and the risk file checked."""
    if record.nc_disposition != "use_as_is_concession":
        return None
    if not record.concession_justification.strip():
        return "A concession needs its justification written down first."
    if record.risk_file_updated in ("", "pending"):
        return ("A concession needs the risk file checked first: set 'Risk file updated' to "
                "Yes or Not needed.")
    return None


def _design_review_complete(record):
    """ISO 13485 7.3.5: a design review records the design reviewed, participants and date."""
    if record.design_element == "review" and not (record.attendees.strip()
                                                  and record.planned_date):
        return "A design review needs its participants and review date."
    return None


def _complaint_reportability(record):
    if record.reportable == "pending":
        return "Reportability must be decided (Yes or No) before closing."
    if record.reportable == "yes" and not record.outgoing_links.filter(
        link_type="escalated_to", target__record_type=INCIDENT
    ).exists():
        return "A reportable complaint needs an 'escalated to' link to an Incident."
    return None


# --- state machines ---------------------------------------------------------

WORKFLOWS = {
    PROBLEM_REPORT: {
        "states": ["open", "triage", "risk_assessment", "in_fix", "verification", "released",
                   "closed", "rejected"],
        "initial": "open",
        "transitions": [
            Transition("triage", "Start triage", ("open",), "triage"),
            Transition("assess_risk", "Move to risk assessment", ("triage",), "risk_assessment",
                       required=("severity", "patient_safety_impact", "software_item",
                                 "software_version")),
            Transition("start_fix", "Start fix", ("risk_assessment",), "in_fix",
                       required=("risk_file_updated",)),
            Transition("verify", "Send to verification", ("in_fix",), "verification",
                       checks=(_has_link("fixed_by", CHANGE_REQUEST, "fixed by Change Request"),)),
            Transition("release", "Mark released", ("verification",), "released",
                       required=("verification_evidence",)),
            Transition("close", "Close", ("released",), "closed", roles=(QA,),
                       signature="Approval", independent=True),
            Transition("reject", "Reject (no action)", ("open", "triage", "risk_assessment"),
                       "rejected", roles=(QA,), signature="Approval", comment_required=True),
        ],
    },
    COMPLAINT: {
        "states": ["received", "investigating", "reportability_decision", "closed"],
        "initial": "received",
        "transitions": [
            Transition("investigate", "Start investigation", ("received",), "investigating",
                       required=("date_aware", "source")),
            Transition("decide", "Ready for reportability decision", ("investigating",),
                       "reportability_decision",
                       required=("investigation_summary", "patient_safety_impact")),
            Transition("close", "Record decision and close", ("reportability_decision",), "closed",
                       roles=(QA, CLINICAL_SAFETY), signature="Reportability decision",
                       required=("reportable", "reportability_rationale"),
                       checks=(_complaint_reportability,)),
        ],
    },
    INCIDENT: {
        "states": ["assessing", "reported", "follow_up", "final_report", "closed"],
        "initial": "assessing",
        "transitions": [
            Transition("report", "Record MHRA report", ("assessing",), "reported",
                       roles=(QA, CLINICAL_SAFETY), signature="Regulatory submission",
                       required=("date_aware", "deadline_category", "mhra_reference")),
            Transition("follow_up", "Start follow-up", ("reported",), "follow_up"),
            Transition("final_report", "Final report submitted", ("follow_up",), "final_report",
                       required=("investigation_summary",)),
            Transition("close", "Close", ("final_report",), "closed", roles=(QA,),
                       signature="Approval", independent=True, required=("resolution",)),
        ],
    },
    CAPA: {
        "states": ["open", "root_cause", "action_plan", "implementing", "effectiveness_check",
                   "closed"],
        "initial": "open",
        "transitions": [
            Transition("investigate", "Start root-cause analysis", ("open",), "root_cause"),
            Transition("plan", "Plan actions", ("root_cause",), "action_plan",
                       required=("root_cause",)),
            Transition("approve_plan", "Approve plan", ("action_plan",), "implementing",
                       roles=(QA,), signature="Approval", independent=True),
            Transition("check", "Start effectiveness check", ("implementing",),
                       "effectiveness_check",
                       required=("verification_evidence", "effectiveness_due")),
            Transition("not_effective", "Not effective: back to implementing",
                       ("effectiveness_check",), "implementing", roles=(QA,),
                       comment_required=True),
            Transition("close", "Effective: close", ("effectiveness_check",), "closed",
                       roles=(QA,), signature="Approval", independent=True,
                       required=("resolution", "risk_file_updated")),
        ],
    },
    CHANGE_REQUEST: {
        "states": ["proposed", "impact_analysis", "approved", "implemented", "verified", "closed",
                   "rejected"],
        "initial": "proposed",
        "transitions": [
            Transition("analyse", "Start impact analysis", ("proposed",), "impact_analysis"),
            Transition("approve", "Approve change", ("impact_analysis",), "approved", roles=(QA,),
                       signature="Approval", independent=True,
                       required=("software_item", "impact_analysis", "risk_file_updated")),
            Transition("implement", "Mark implemented", ("approved",), "implemented"),
            Transition("verify", "Mark verified", ("implemented",), "verified",
                       required=("verification_evidence",)),
            Transition("close", "Close", ("verified",), "closed", roles=(QA,),
                       signature="Approval", required=("fix_version",)),
            Transition("reject", "Reject", ("proposed", "impact_analysis"), "rejected",
                       roles=(QA,), signature="Approval", comment_required=True),
        ],
    },
    PMS_ACTIVITY: {
        "states": ["todo", "in_progress", "review", "done"],
        "initial": "todo",
        "transitions": [
            Transition("start", "Start", ("todo",), "in_progress"),
            Transition("submit", "Submit for review", ("in_progress",), "review",
                       required=("investigation_summary",)),
            Transition("rework", "Send back", ("review",), "in_progress", roles=(QA,),
                       comment_required=True),
            Transition("complete", "Approve and complete", ("review",), "done", roles=(QA,),
                       signature="Review", independent=True),
        ],
    },
    INTERNAL_AUDIT: {
        "states": ["planned", "in_progress", "report_issued", "closed"],
        "initial": "planned",
        "transitions": [
            Transition("start", "Start audit", ("planned",), "in_progress",
                       required=("audit_scope", "auditee", "owner", "planned_date"),
                       checks=(_auditor_independent,)),
            Transition("report", "Issue audit report", ("in_progress",), "report_issued",
                       required=("investigation_summary",)),
            Transition("close", "Close audit", ("report_issued",), "closed", roles=(QA,),
                       signature="Approval", independent=True, required=("resolution",)),
        ],
    },
    MANAGEMENT_REVIEW: {
        "states": ["planned", "held", "closed"],
        "initial": "planned",
        "transitions": [
            Transition("hold", "Record review held", ("planned",), "held", roles=(QA,),
                       required=("planned_date", "attendees", "review_inputs")),
            Transition("close", "Record outputs and close", ("held",), "closed", roles=(QA,),
                       signature="Approval", required=("resolution", "resource_needs")),
        ],
    },
    NONCONFORMANCE: {
        "states": ["open", "evaluation", "disposition", "verification", "closed", "rejected"],
        "initial": "open",
        "transitions": [
            Transition("evaluate", "Start evaluation", ("open",), "evaluation"),
            Transition("decide", "Record disposition", ("evaluation",), "disposition", roles=(QA,),
                       signature="Disposition approval", independent=True,
                       required=("investigation_summary", "nc_disposition"),
                       checks=(_concession_justified,)),
            Transition("verify", "Verify disposition", ("disposition",), "verification",
                       required=("verification_evidence",)),
            Transition("close", "Close", ("verification",), "closed", roles=(QA,),
                       signature="Approval", independent=True, required=("resolution",)),
            Transition("reject", "Reject (not nonconforming)", ("open", "evaluation"), "rejected",
                       roles=(QA,), signature="Approval", comment_required=True),
        ],
    },
    DESIGN_CONTROL: {
        "states": ["draft", "in_review", "closed", "rejected"],
        "initial": "draft",
        "transitions": [
            Transition("submit", "Submit for review", ("draft",), "in_review",
                       required=("design_element", "acceptance_criteria"),
                       checks=(_design_review_complete,)),
            Transition("approve", "Approve", ("in_review",), "closed", roles=(QA,),
                       signature="Design approval", independent=True,
                       required=("investigation_summary",)),
            Transition("reject", "Reject", ("in_review",), "rejected", roles=(QA,),
                       signature="Approval", comment_required=True),
        ],
    },
}


def initial_state(record_type: str) -> str:
    return WORKFLOWS[record_type]["initial"]


def all_transitions(record_type: str):
    return WORKFLOWS[record_type]["transitions"]


def get_transition(record_type: str, name: str) -> Transition:
    for t in all_transitions(record_type):
        if t.name == name:
            return t
    raise KeyError(f"Unknown transition {name!r} for {record_type}")


def state_choices():
    seen, out = set(), []
    for wf in WORKFLOWS.values():
        for s in wf["states"]:
            if s not in seen:
                seen.add(s)
                out.append((s, s.replace("_", " ").capitalize()))
    return out
