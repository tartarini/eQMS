"""Documentation route: how far a device's documentation has got, stage by stage.

A device follows one of two routes, set on its record (``Device.development_route``):

- **Greenfield**, documentation from the start of development: six stages, 1 to 6 (set-up,
  intended purpose and classification, requirements and design, risk, verification and
  evidence, release and post-market).
- **Retrofit**, an existing device whose documentation is reconstructed: seven steps, A to G
  (gap assessment, baseline, then reconstructing purpose, design, risk and evidence, then
  closing the gaps).

Each stage is a list of checks worked out from what the QMS already holds (the device record,
its team, documents, hazards, SOUP, records and technical file builds). Checks marked as gate
checks are the ones a stage's approver gate relies on. Where the route has an approver gate
for a stage (``models.devices.GATES_BY_ROUTE``), the stage also carries that gate's signed
status, so the page shows the checks and the sign-off together.

Read-only: nothing is stored or created here, so progress can't drift from the records it
describes. A stage's gate checks must pass before its approver gate can be signed
(``tasks.approve_gate`` asks ``gate_check_failures``). The checks don't replace
``techfile.completeness_checks``, which decides whether a technical file build can be approved.
"""
from django.db.models import Q
from django.urls import reverse

from . import workflow as wf
from .models import GATES_BY_ROUTE, DocumentVersion, Record, StageGate


def _item(label, done, url_name="", gate=False, detail=""):
    return {"label": label, "done": bool(done), "url_name": url_name, "gate": gate,
            "detail": detail}


# The steps of each route, in order: (key, short name). Greenfield stages are numbered 1 to 6,
# Retrofit steps lettered A to G.
ROUTE_STEPS = {
    "greenfield": [("1", "Set-up"), ("2", "Purpose and class"), ("3", "Requirements and design"),
                   ("4", "Risk"), ("5", "Verification and evidence"), ("6", "Release and PMS")],
    "retrofit": [("A", "Gap assessment"), ("B", "Baseline"), ("C", "Purpose and class"),
                 ("D", "Requirements and SOUP"), ("E", "Risk"), ("F", "Test evidence"),
                 ("G", "Close gaps")],
}
# Which step a technical file section, record type or document type belongs to, for each route.
SECTION_STEP = {
    "greenfield": {"description": "2", "labelling": "2", "design": "3", "gspr": "3", "risk": "4",
                   "verification": "5", "clinical": "5", "pms": "6", "declaration": "6"},
    "retrofit": {"description": "C", "labelling": "C", "design": "D", "gspr": "D", "risk": "E",
                 "verification": "F", "clinical": "G", "pms": "G", "declaration": "G"},
}
RECORD_STEP = {
    "greenfield": {wf.CHANGE_REQUEST: "6", wf.PROBLEM_REPORT: "6", wf.COMPLAINT: "6",
                   wf.INCIDENT: "6", wf.CAPA: "6", wf.PMS_ACTIVITY: "6", wf.NONCONFORMANCE: "6",
                   wf.DESIGN_CONTROL: "3"},
    "retrofit": {wf.CHANGE_REQUEST: "B", wf.PROBLEM_REPORT: "G", wf.COMPLAINT: "G",
                 wf.INCIDENT: "G", wf.CAPA: "G", wf.PMS_ACTIVITY: "G", wf.NONCONFORMANCE: "G",
                 wf.DESIGN_CONTROL: "D"},
}


def step_for(route, *, section="", record_type="", doc_type="", build=False) -> str:
    """The step key a task belongs to on ``route``, or "" for work that isn't on the route
    (QMS-wide documents, internal audits, management reviews)."""
    if route not in ROUTE_STEPS:
        return ""
    if build:
        return "6" if route == "greenfield" else "G"
    if doc_type == "GAP":
        return "A" if route == "retrofit" else ""
    if record_type:
        return RECORD_STEP[route].get(record_type, "")
    return SECTION_STEP[route].get(section, "")


def placement(route, step) -> tuple:
    """(label, position) for a step, e.g. ("Stage 3 · Requirements and design", 3). Position is
    1 to 7 along the route, for colouring; ("", 0) when there is no step."""
    for position, (key, name) in enumerate(ROUTE_STEPS.get(route, []), start=1):
        if key == step:
            prefix = "Stage" if route == "greenfield" else "Step"
            return f"{prefix} {key} · {name}", position
    return "", 0


def _facts(device, data, checks):
    """What the checks are worked out from, computed once for both routes."""
    sections = data["sections"]
    hazards = data["hazards"]
    controls = [c for h in hazards for c in h.controls.all()]
    team_size = device.memberships.filter(active=True).count()
    errors = [c for c in checks if c["level"] == "error"]
    approved_builds = [b for b in data["builds"] if b.status == "approved"]
    # A gap assessment is a device document of the Gap assessment type. Documents titled "gap
    # assessment" before that type existed still count, since their type can't be changed.
    gap_assessment = DocumentVersion.objects.filter(
        Q(document__doc_type="GAP") | Q(document__title__icontains="gap assessment"),
        status="effective", document__obsolete=False, document__device=device,
    ).select_related("document").first()
    change_requests = Record.objects.filter(device=device,
                                            record_type=wf.CHANGE_REQUEST).count()
    return {
        "sections": sections, "hazards": hazards, "controls": controls,
        "team_size": team_size, "errors": errors, "approved_builds": approved_builds,
        "safety_problems": [r for r in data["open_anomalies"]
                            if r.patient_safety_impact == "yes"],
        "on_market": device.regulatory_status == "on_market", "soup": data["soup"],
        "pms": data["pms_open"] or data["pms_done"], "gap_assessment": gap_assessment,
        "change_requests": change_requests,
    }


def _setup_items(device, f):
    return [
        _item("Our economic operator role is set", device.operator_role_list(), "device_edit"),
        _item("Legal manufacturer recorded", device.manufacturer.strip(), "device_edit"),
        _item("Device description recorded", device.description.strip(), "device_edit"),
        _item("Expected lifetime set", device.expected_lifetime_years, "device_edit"),
        _item("Device team has members", f["team_size"], "device_detail",
              detail=f"{f['team_size']} member{'s' if f['team_size'] != 1 else ''}"),
    ]


def _purpose_items(device):
    return [
        _item("Intended purpose", device.intended_purpose.strip(), "device_edit"),
        _item("Intended users", device.intended_users.strip(), "device_edit"),
        _item("Intended patient population", device.patient_population.strip(), "device_edit"),
        _item("Classified in every market it's placed on",
              device.classifications() and not device.classification_gaps(), "device_edit",
              gate=True, detail=device.classification_summary()),
        _item("Classification rationale recorded", device.classification_rule.strip(),
              "device_edit", gate=True),
        _item("IEC 62304 software safety class set", device.software_safety_class,
              "device_edit"),
    ]


def _design_items(device, f, gate=False):
    return [
        _item("Software items (architecture) listed", device.software_item_list(),
              "device_edit", gate=gate),
        _item("Effective design document in the technical file", f["sections"].get("design"),
              "document_list", gate=gate),
        _item("Effective GSPR checklist", f["sections"].get("gspr"), "document_list"),
        _item("SOUP items linked", f["soup"], "supplier_list", gate=gate,
              detail=f"{len(f['soup'])} item(s)"),
        _item("Current software version recorded", device.current_version.strip(),
              "device_edit"),
    ]


def _risk_items(f, verified_is_gate=False):
    hazards, controls = f["hazards"], f["controls"]
    return [
        _item("Risk register has hazards", hazards, "hazard_list",
              detail=f"{len(hazards)} active"),
        _item("Every hazard has a risk control",
              hazards and all(h.controls.all() for h in hazards), "hazard_list", gate=True),
        _item("Every risk control verified", controls and all(c.verified for c in controls),
              "hazard_list", gate=verified_is_gate,
              detail=f"{sum(c.verified for c in controls)} of {len(controls)}"),
        _item("Every residual risk accepted",
              hazards and all(h.status == "accepted" for h in hazards), "hazard_list"),
        _item("Effective risk management file", f["sections"].get("risk"), "document_list"),
    ]


def _verification_item(f, gate=True):
    return _item("Effective verification and validation evidence",
                 f["sections"].get("verification"), "document_list", gate=gate)


def _clinical_item(f, gate=True):
    return _item("Effective clinical evaluation and usability evidence",
                 f["sections"].get("clinical"), "document_list", gate=gate)


def _safety_problem_item(f):
    return _item("No open problem with patient-safety impact", not f["safety_problems"],
                 "record_list", detail=", ".join(r.ref for r in f["safety_problems"][:5]))


def _release_items(f):
    errors, builds = f["errors"], f["approved_builds"]
    return [
        _item("Labelling and IFU effective", f["sections"].get("labelling"), "document_list"),
        _item("Post-market surveillance scheduled", f["pms"], "record_list"),
        _item("Effective PMS plan", f["sections"].get("pms"), "document_list"),
        _item("Declaration of conformity effective" if f["on_market"]
              else "Declaration of conformity (needed before placing on the market)",
              f["sections"].get("declaration"), "document_list"),
        _item("Technical file has no completeness errors", not errors, gate=True,
              detail=f"{len(errors)} error(s)" if errors else ""),
        _item("A technical file build is approved", builds,
              detail=builds[0].label if builds else ""),
    ]


def _greenfield(device, f):
    return [
        ("1", "Organisation and device set-up", "Set-up",
         "Economic operator roles, device record, team, expected lifetime.",
         _setup_items(device, f)),
        ("2", "Intended purpose and classification", "Purpose and class",
         "Intended use, classification in each market, software safety class.",
         _purpose_items(device)),
        ("3", "Requirements, design and software items", "Requirements and design",
         "Requirements with IDs and tests, design, architecture.", _design_items(device, f)),
        ("4", "Hazards, controls and residual risk", "Risk",
         "Hazards from intended use and misuse. Starts at concept.", _risk_items(f)),
        ("5", "Verify, validate and show performance", "Verification and evidence",
         "Tests traced to requirements, usability, clinical evidence.",
         [_verification_item(f), _clinical_item(f), _safety_problem_item(f)]),
        ("6", "Release, technical file and surveillance", "Release and PMS",
         "Freeze release, build technical file, PMS schedule, change control.",
         _release_items(f)),
    ]


def _retrofit(device, f):
    gap = f["gap_assessment"]
    return [
        ("A", "Gap assessment", "Gap assessment",
         "Score every expected document: current, out of date, knowledge only, or missing.",
         [_item("Effective gap assessment document for this device", gap, "document_list",
                gate=True, detail=gap.document.number if gap else
                "an effective Gap assessment document for this device")]),
        ("B", "Freeze and baseline the release", "Baseline",
         "Record the release in use, and put every change from now on under change control.",
         [_item("Current software version recorded as the baseline",
                device.current_version.strip(), "device_edit", gate=True,
                detail=device.current_version.strip()),
          _item("Change control in use: a change request is recorded", f["change_requests"],
                "record_list", gate=True, detail=f"{f['change_requests']} recorded")]
         + _setup_items(device, f)),
        ("C", "Reconstruct intended purpose and classification", "Purpose and class",
         "From labelling, marketing material and design history; signed by current management.",
         _purpose_items(device)),
        ("D", "Reconstruct requirements, design and SOUP", "Requirements and SOUP",
         "From the code, tests, API documentation and dependency manifests.",
         _design_items(device, f, gate=True)),
        ("E", "Reconstruct the risk file and check controls", "Risk",
         "Hazards from purpose, incidents and code paths; each control checked against code.",
         _risk_items(f, verified_is_gate=True)),
        ("F", "Test evidence against the baseline", "Test evidence",
         "Run the tests against the baseline, trace them, record known limitations.",
         [_verification_item(f), _safety_problem_item(f)]),
        ("G", "Close the gaps and assess regulatory position", "Close gaps",
         "Close gaps by priority, then decide what the device needs to stay on the market.",
         [_clinical_item(f, gate=False)] + _release_items(f)),
    ]


def _url(device, name):
    if name == "device_detail":
        return reverse("qms:device_detail", args=[device.code]) + "#team"
    if name:
        return reverse(f"qms:{name}", args=[device.code] if name == "device_edit" else [])
    return ""


def stages(device, data: dict, checks: list) -> list:
    """The stages of ``device``'s documentation route. ``data`` and ``checks`` are
    ``techfile.gather`` and ``techfile.completeness_checks`` for the same device, so the page
    works them out once.

    Each stage: {"number" ("1"-"6" or "A"-"G"), "title", "short", "summary", "items", "done",
    "total", "percent", "status" ("todo", "progress" or "done"), "gate" (the gate checks' labels
    or ""), "gate_passed", "signoff"}. ``signoff`` is None for a stage with no approver gate,
    else {"name", "approver_role", "status" ("open" or "approved"), "approved_by",
    "approved_at", "state"}; ``state`` is "approved", "ready" (checks pass, awaiting sign-off),
    "blocked" (gate checks not passing, so it can't be signed yet) or "stale" (approved, but the checks no longer pass).
    """
    f = _facts(device, data, checks)
    route = device.development_route
    raw = _retrofit(device, f) if route == "retrofit" else _greenfield(device, f)
    defined = {stage: (name, role) for stage, name, role in GATES_BY_ROUTE.get(route, [])}
    signed = {g.stage: g for g in StageGate.objects.filter(device=device, route=route)
              .select_related("approved_by")}

    out = []
    for number, title, short, summary, items in raw:
        for i in items:
            i["url"] = _url(device, i.pop("url_name"))
        done = sum(i["done"] for i in items)
        total = len(items)
        gate_checks = [i for i in items if i["gate"]]
        gate_passed = all(i["done"] for i in gate_checks)
        signoff = None
        if number in defined:
            row = signed.get(number)
            name, role = defined[number]
            approved = row is not None and row.status == "approved"
            signoff = {
                "name": row.name if row else name,
                "approver_role": row.approver_role if row else role,
                "status": "approved" if approved else "open",
                "approved_by": row.approved_by if approved else None,
                "approved_at": row.approved_at if approved else None,
                "state": ("stale" if approved and not gate_passed else
                          "approved" if approved else
                          "ready" if gate_passed else "blocked"),
            }
        out.append({
            "number": number, "title": title, "short": short, "summary": summary,
            "items": items, "done": done, "total": total,
            "percent": round(100 * done / total),
            "status": "done" if done == total else ("progress" if done else "todo"),
            "gate": " and ".join(g["label"].lower() for g in gate_checks),
            "gate_passed": gate_passed, "signoff": signoff,
        })
    return out


def overall(stage_list: list) -> int:
    """Overall progress, as the share of all checks that pass (0-100)."""
    total = sum(s["total"] for s in stage_list)
    return round(100 * sum(s["done"] for s in stage_list) / total) if total else 0


def current_stage(stage_list: list):
    """The first stage that isn't finished, or None when all are."""
    return next((s for s in stage_list if s["status"] != "done"), None)


def by_number(stage_list: list) -> dict:
    """The stages keyed by number, for showing a gate's checks beside the gate."""
    return {s["number"]: s for s in stage_list}


def gate_check_failures(device, stage: str) -> list:
    """Labels of the gate checks that don't pass for ``stage`` of ``device``'s route; empty
    when they all pass. Used to stop an approver gate being signed while its checks fail."""
    from . import techfile  # techfile imports models only; imported here to keep this light
    data = techfile.gather(device)
    found = by_number(stages(device, data, techfile.completeness_checks(device, data))).get(stage)
    if found is None:
        return []
    return [i["label"] for i in found["items"] if i["gate"] and not i["done"]]
