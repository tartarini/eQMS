"""Documentation route: how far a device's documentation has got, stage by stage.

The six stages of documenting a software medical device from the start (the "greenfield"
route): set-up, intended purpose and classification, requirements and design, risk management,
verification and evidence, then release and post-market. Each stage is a list of checks worked
out from what the QMS already holds (the device record, its team, documents, hazards, SOUP,
records and technical file builds). Some checks are gates: the stage shouldn't be treated as
finished, and the next one relied on, until they pass.

Read-only: nothing is stored, so progress can't drift from the records it describes, and the
page never changes a status. It complements, and doesn't replace, ``techfile.completeness_checks``
(which decides whether a technical file build can be approved).
"""
from django.urls import reverse


def _item(label, done, url_name="", gate=False, detail=""):
    return {"label": label, "done": bool(done), "url_name": url_name, "gate": gate,
            "detail": detail}


def stages(device, data: dict, checks: list) -> list:
    """The six stages for ``device``. ``data`` and ``checks`` are ``techfile.gather`` and
    ``techfile.completeness_checks`` for the same device, so the page works them out once.

    Each stage: {"number", "title", "summary", "items", "done", "total", "percent", "status",
    "gate"}; ``gate`` is the label of the stage's gate check, or "".
    """
    sections = data["sections"]
    hazards = data["hazards"]
    controls = [c for h in hazards for c in h.controls.all()]
    team_size = device.memberships.filter(active=True).count()
    errors = [c for c in checks if c["level"] == "error"]
    safety_problems = [r for r in data["open_anomalies"] if r.patient_safety_impact == "yes"]
    approved_builds = [b for b in data["builds"] if b.status == "approved"]
    on_market = device.regulatory_status == "on_market"

    raw = [
        (1, "Organisation and device set-up",
         "Economic operator roles, device record, team, expected lifetime.", [
             _item("Our economic operator role is set", device.operator_role_list(),
                   "device_edit"),
             _item("Legal manufacturer recorded", device.manufacturer.strip(), "device_edit"),
             _item("Device description recorded", device.description.strip(), "device_edit"),
             _item("Expected lifetime set", device.expected_lifetime_years, "device_edit"),
             _item("Device team has members", team_size, "device_detail",
                   detail=f"{team_size} member{'s' if team_size != 1 else ''}"),
         ]),
        (2, "Intended purpose and classification",
         "Intended use, classification in each market, software safety class.", [
             _item("Intended purpose", device.intended_purpose.strip(), "device_edit"),
             _item("Intended users", device.intended_users.strip(), "device_edit"),
             _item("Intended patient population", device.patient_population.strip(),
                   "device_edit"),
             _item("Classified in every market it's placed on",
                   device.classifications() and not device.classification_gaps(),
                   "device_edit", gate=True,
                   detail=device.classification_summary()),
             _item("Classification rationale recorded", device.classification_rule.strip(),
                   "device_edit", gate=True),
             _item("IEC 62304 software safety class set", device.software_safety_class,
                   "device_edit"),
         ]),
        (3, "Requirements, design and software items",
         "Requirements with IDs and tests, design, architecture.", [
             _item("Software items (architecture) listed", device.software_item_list(),
                   "device_edit"),
             _item("Effective design document in the technical file", sections.get("design"),
                   "document_list"),
             _item("Effective GSPR checklist", sections.get("gspr"), "document_list"),
             _item("SOUP items linked", data["soup"], "supplier_list",
                   detail=f"{len(data['soup'])} item(s)"),
             _item("Current software version recorded", device.current_version.strip(),
                   "device_edit"),
         ]),
        (4, "Hazards, controls and residual risk",
         "Hazards from intended use and misuse. Starts at concept.", [
             _item("Risk register has hazards", hazards, "hazard_list",
                   detail=f"{len(hazards)} active"),
             _item("Every hazard has a risk control",
                   hazards and all(h.controls.all() for h in hazards), "hazard_list",
                   gate=True),
             _item("Every risk control verified",
                   controls and all(c.verified for c in controls), "hazard_list",
                   detail=f"{sum(c.verified for c in controls)} of {len(controls)}"),
             _item("Every residual risk accepted",
                   hazards and all(h.status == "accepted" for h in hazards), "hazard_list"),
             _item("Effective risk management file", sections.get("risk"), "document_list"),
         ]),
        (5, "Verify, validate and show performance",
         "Tests traced to requirements, usability, clinical evidence.", [
             _item("Effective verification and validation evidence",
                   sections.get("verification"), "document_list", gate=True),
             _item("Effective clinical evaluation and usability evidence",
                   sections.get("clinical"), "document_list", gate=True),
             _item("No open problem with patient-safety impact", not safety_problems,
                   "record_list",
                   detail=", ".join(r.ref for r in safety_problems[:5])),
         ]),
        (6, "Release, technical file and surveillance",
         "Freeze release, build technical file, PMS schedule, change control.", [
             _item("Labelling and IFU effective", sections.get("labelling"), "document_list"),
             _item("Post-market surveillance scheduled", data["pms_open"] or data["pms_done"],
                   "record_list"),
             _item("Effective PMS plan", sections.get("pms"), "document_list"),
             _item("Declaration of conformity effective" if on_market
                   else "Declaration of conformity (needed before placing on the market)",
                   sections.get("declaration"), "document_list"),
             _item("Technical file has no completeness errors", not errors, gate=True,
                   detail=f"{len(errors)} error(s)" if errors else ""),
             _item("A technical file build is approved", approved_builds,
                   detail=approved_builds[0].label if approved_builds else ""),
         ]),
    ]

    out = []
    for number, title, summary, items in raw:
        for i in items:
            name = i.pop("url_name")
            if name == "device_detail":
                i["url"] = reverse("qms:device_detail", args=[device.code]) + "#team"
            elif name:
                i["url"] = reverse(f"qms:{name}",
                                   args=[device.code] if name == "device_edit" else [])
            else:
                i["url"] = ""
        done = sum(i["done"] for i in items)
        total = len(items)
        gates = [i for i in items if i["gate"]]
        out.append({
            "number": number, "title": title, "summary": summary, "items": items,
            "done": done, "total": total, "percent": round(100 * done / total),
            "status": "done" if done == total else ("progress" if done else "todo"),
            "gate": " and ".join(g["label"].lower() for g in gates) if gates else "",
            "gate_passed": all(g["done"] for g in gates),
        })
    return out


def overall(stage_list: list) -> int:
    """Overall progress, as the share of all checks that pass (0-100)."""
    total = sum(s["total"] for s in stage_list)
    return round(100 * sum(s["done"] for s in stage_list) / total) if total else 0


def current_stage(stage_list: list):
    """The first stage that isn't finished, or None when all are."""
    return next((s for s in stage_list if s["status"] != "done"), None)

