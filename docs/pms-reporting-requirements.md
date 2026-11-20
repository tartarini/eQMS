# Post-Market Surveillance Reporting Requirements (Research Note)

Status: research input for the PMS feature. Not a regulatory opinion. Every regulatory statement carries a status tag:

- **[P]** primary text read (via legislation.gov.uk, through a summarising fetch; re-check the wording against the official text before release)
- **[S]** secondary source only (vendor, consultancy, or guide)
- **[V]** verify: not confirmed from a source in this research; do not rely on it

Research date: 2026-11-13. Vendor claims are marketing unless stated otherwise.

---

## 1. Competitor analysis

### 1.1 Summary

Eight products were looked at. Public materials were thin for most of them: none of the vendors' public pages confirmed an end-user (clinician, patient, carer) complaint portal with reporter 2FA or SSO. Where a claim is not documented, the cell says "not found" rather than "no". A product demo or trial account is needed to close these gaps.

### 1.2 Comparison table

| Product | Complaint / feedback / AE intake captures | External user portal | Reporter identity, 2FA, SSO | Links to external issue trackers | Notably missing or unclear | Sources |
|---|---|---|---|---|---|---|
| Greenlight Guru | Complaints, reviews, evaluations, investigations; complaints linked to CAPA and risk (vendor claim) | Not found | Not found | Not found | Public material does not describe intake fields or an external form. Feedback vs. complaint distinction is explained in blog form | https://greenlight.guru/complaint-management-software ; https://www.greenlight.guru/blog/understanding-and-handling-different-types-of-feedback |
| MasterControl | Cloud complaints module tracking complaints to resolution; links to CAPA and Risk modules; pages state a complaint may turn out to be a reportable adverse event | Not found | Not found | Not found | No public description of a customer-facing form or of MDR timeline support | https://www.mastercontrol.com/complaints-software ; https://www.mastercontrol.com/complaints-software/complaint-handling/ |
| Qualio | Claims automatic complaint workflow when complaints are logged elsewhere; configurable workflows for AE investigation, CAPA and health-authority notification | Not found | Not found | Not found | Reportability decision logic and submission timelines not described in the material found | https://www.qualio.com/product/pharmacovigilance-software ; https://www.qualio.com/blog/fda-medical-device-reporting-procedures |
| Veeva Vault QualityOne (Quality Cloud) | Complaint Intake records created from an integrated third-party system (for example a company website), from emails to a configured complaint inbox, or manually. A configurable assessment promotes intake to one or more Complaint records. Complaint Contacts track reporters and complainants and are required for external notifications | Not found for complainants. Supplier portal covers nonconformances only | Not found | Integration with third-party systems is the intake route; no tracker link documented | No direct complainant-facing portal described. Intake depends on a company-built website integration | https://quality.veevavault.help/en/lr/28400/ ; https://quality.veevavault.help/en/gr/928400/ ; https://www.veeva.com/QMS |
| Ideagen Quality Management (formerly Q-Pulse) | Customer complaints and feedback module with response-time monitoring; complaints linked to CAPA with no separate complaint log | Not found. "Customer portal" in results is the Ideagen Help support site, not a complaint portal | Not found | Not found | Medical-device complaint workflow (MDR, 21 CFR 820.198) not described in sources found | https://www.applytosupply.digitalmarketplace.service.gov.uk/g-cloud/services/567215567041443 ; https://www.capterra.com/p/155354/Ideagen-Quality-Management/reviews/ |
| Sparta Systems TrackWise Digital (TWD Intake) | Browser-based intake for staff to report quality or compliance issues from tablets and phones; configurable form; feeds TrackWise workflows; ML auto-categorisation of complaints (vendor claim) | Not found. Intake datasheet frames it as employee-facing | Not found. Datasheet dated 12/23 and now carries Honeywell branding, so may be out of date | Not found | Whether external submission is possible, and how it is secured, is not confirmed | https://info.spartasystems.com/rs/093-RAU-212/images/TrackWise_Digital_TWD_Intake.pdf ; https://www.spartasystems.com/complaint-management-software/ |
| IQVIA SmartSolve | Standardised web intake forms and decision trees that separate complaints from adverse events (search snippet of vendor fact sheet) | Not confirmed from body text | Not confirmed | Not found | Fact sheet not read in full; claims unverified | https://www.iqvia.com/library/fact-sheets/smartsolve-complaint-management |
| ARIS Global Product Complaints | Intake from email, call centre and portals; links complaints to adverse-event cases (search snippet of vendor page) | Portal intake claimed (snippet only) | Not confirmed | Not found | Page not read in full | https://www.arisglobal.com/product-complaints/ |
| EmpowerQMS | Not researched: search returned no product-specific results | Not researched | Not researched | Not researched | Requires a direct search of the vendor site | none |

### 1.3 Patterns relevant to this feature

- Intake is usually an internal, staff-facing form. Customer or clinician access is typically done by building a website form that feeds the QMS (Veeva, TrackWise, ARIS). This supports keeping end-user intake as a simple separate path.
- Complaint versus adverse event is separated by a decision step, not by the form. Veeva (complaint promotion assessment), IQVIA (decision trees) and MasterControl (complaint may become AE) all treat it this way.
- Complaint contacts are a separate record from the complaint. Veeva's model (Complaint Contacts) is a useful pattern for reporter identity.
- Gap across the set: no public evidence of reporter 2FA or SSO on the intake side. Treat as an open differentiator, and verify in demos.

---

## 2. Regulatory requirements matrix

Deadlines run from the manufacturer's awareness unless stated. The EU and UK texts are close to identical for serious incidents; the UK text was read via legislation.gov.uk [P, via summary].

| # | Requirement | Source and status | Field or information it implies | Deadline |
|---|---|---|---|---|
| R1 | Serious incident reporting (general) | EU MDR Art. 87 [S, not read in primary text; verify]. UK Medical Devices Regulations 2002, reg. 44ZH(3)(a)-(b) [P] | Device identifier (UDI-DI and UDI-PI or lot/serial), software version, date of awareness, date of event, description, patient or user outcome, causal relationship assessment, reporting Member State or country, reporter type | Immediately after the causal (or reasonably possible causal) relationship is established, and no later than 15 days after awareness [P for UK; EU verify] |
| R2 | Serious incident: death or unanticipated serious deterioration in health | EU Art. 87 [S; verify]. UK reg. 44ZH(5) [P] | Patient outcome flag (death / serious deterioration), age range and sex (no name), clinical sequence | No later than 10 days after awareness [P for UK; EU verify] |
| R3 | Serious incident: serious public health threat | EU Art. 87 [S; verify]. UK reg. 44ZH(4) [P] | Threat flag, affected population estimate, cross-border indicator | No later than 2 days after awareness [P for UK; EU verify] |
| R4 | Incomplete initial report permitted where needed to meet deadlines, followed by a complete report | EU Art. 87 [S; verify wording] | Initial/follow-up report flag, missing-fields list, follow-up due date | Complete report to follow (date not in sources) [V] |
| R5 | Field safety corrective action (FSCA) reporting | UK reg. 44ZJ(1), (3), (4), (7) [P]. EU Art. 87 [S] | FSCA type, field safety notice (copy), initial report, action date, number of devices affected, final report | Initial report before the FSCA; urgent exception allows report after the FSCA; final report after completion (UK 44ZJ) [P]. EU: "without undue delay" [S] |
| R6 | FSCA taken outside GB, same model | UK reg. 44ZK [P: obligation exists; timing not stated in the text read] | Country list, device model, action date | [V] |
| R7 | Trend reporting | EU MDR Art. 88 [S: significant increase in frequency or severity of non-serious incidents or expected side effects that could affect benefit-risk]. UK reg. 44ZN(1), (4) [P] | Event counts and rates by period, severity, software version, device model, PMS period, statistical method note | No fixed day count found [V]. Secondary source says the UK duty applies from 16 June 2026 [S; verify] |
| R8 | Periodic safety update report (PSUR) | EU MDR Art. 86 [S: class IIa updated when necessary and at least every two years; class IIb and III annually]. UK reg. 44ZM(6)-(8) [P: general first PSUR within 1 year, then yearly; class IIa first within 2 years, then every 2 years] | Exposure data (units placed, users, usage), cumulative incident data, benefit-risk conclusion, software versions covered | As above. EU class IIa / IIb / III intervals [V against primary text] |
| R9 | Analysis of serious incidents and FSCAs | EU MDR Art. 89 [S: investigate without delay after reporting]. Article number and content: [V] | Investigation record link, root cause, CAPA link | "Without delay" [S] |
| R10 | Article 90 and Article 92 (EU) | Not confirmed. Art. 92 described in a secondary source as the electronic system (EUDAMED) for PSURs and vigilance reports [S; V] | EUDAMED submission record ID | [V] |
| R11 | Annex III: PMS (complaints, feedback, literature, PMS data sources) | EU MDR Annex III [V: not read] | Source-of-data field (complaint, feedback, literature, registry, user survey), PMS plan ID | [V] |
| R12 | UK vigilance channel | MHRA Manufacturer's Online Reporting Environment (MORE) is the only accepted route for GB and NI device reports [S: BSIR summary of MHRA guidance; verify on gov.uk] | Regulator reference number, submission date, channel = MORE | Follows R1 / R5 timelines [P] |
| R13 | UK adverse incident definition and scope | Definition: an event that caused or almost caused injury, or wrong or delayed diagnosis or treatment [S: BSIR]. Scope includes instructions-for-use and packaging problems where harm occurred or might have occurred [S; verify] | Near-miss flag, IFU or labelling problem flag | [V] |
| R14 | Northern Ireland reporting | EU forms within MORE for NI serious incidents, FSCAs and trends [S]. From 1 August 2025, NI healthcare staff report to Yellow Card under their organisation's policy [S] | Country = NI routing | [V] |
| R15 | MHRA Yellow Card for devices | Yellow Card is the MHRA scheme; manufacturers report via MORE [S: MHRA pages listed]. Reporting by end users (clinicians, patients) through the public Yellow Card route [S] | End-user route to Yellow Card: reporter type, device name, free text, date | [V] |
| R16 | ISO 13485:2016 clause 8.2.1 feedback | Clause number from ISO 13485:2016 as commonly cited [V: standard text not read; some sources mislabel the complaint clause as 8.2.1] | Feedback record, source, date, outcome of use | [V] |
| R17 | ISO 13485:2016 clause 8.2.2 complaint handling | Described by CASRAI and advisera as the complaint procedure: timely handling under regulatory requirements; documented decision on reportability; investigation and routing of serious complaints [S] | Complaint ID, intake channel and date, reporter identity record, investigation record, reportability decision with rationale and approver, closure record, link to CAPA | No day count in standard [S] |
| R18 | ISO 13485:2016 clause 8.2.3 reporting to regulatory authorities | Described as the reporting requirement [S: CASRAI]. Specific timelines come from the regulation, not the clause [S] | Reporting decision, regulator, submission date, reference | Per regulation (see R1 to R3, R11) [V] |
| R19 | IEC 82304-1 health software (post-market) | Clause 8 covers post-market activities: 8.2 software maintenance, 8.3 re-validation, 8.4 post-market communication, 8.5 decommissioning (table of contents, DIN copy) [S]. A third-party guide places feedback and complaints in the post-market clause but numbers it as clause 9 [S; conflicts]. Complaint wording not confirmed [V] | Software version, maintenance release ID, re-validation record, user communication log (field notice), decommissioning date | [V] |
| R20 | IMDRF adverse event terminology (AET) | IMDRF/AE WG/N43FINAL:2020 (Edition 4) annexes A to G: A device problem, B to D cause investigation, E and F health effects (clinical signs or conditions; impact), G components [S; code values not read] | Device problem code, health-effect code, component code, cause-investigation type and findings | None [S] |
| R21 | IMDRF common data set for AE exchange | IMDRF/AET WG/N85 FINAL:2024 [S: title only; primary document not read] | Common data elements (field list not read) | None [S] |
| R22 | FDA 21 CFR 803 (comparison only) | 803.50: 30 calendar days for death, serious injury, malfunction reportable events, from awareness [S: FDA guidance summary; eCFR text partly visible]. 803.53: 5 work days when remedial action is needed or FDA requests it [S]. Awareness: any employee [S] | Same core fields as R1, plus malfunction flag and "would likely recur" assessment | 30 calendar days; 5 work days (conditional) [S; verify] |
| R23 | 21 CFR 820.198 complaint files (comparison) | Complaint procedures and a formally designated unit; complaint files [S] | Complaint file completeness, designated unit owner | [V] |

### 2.1 Items to resolve before build

- Confirm EU Art. 87 paragraphs 1 to 6 text and deadlines against EUR-Lex (R1 to R4 and R10 are secondary-sourced for the EU).
- Confirm MDR Arts. 89, 90, 92 and Annex III content (R9 to R11). Titles and roles are not verified here.
- Check the status of the 2026 EU Council proposal on MDR/IVDR simplification, which may change PSUR and trend-reporting rules (R7, R8). Not confirmed as adopted.
- Check MHRA GB guidance for the current trend and PSUR start dates (R7, R8), which one secondary source gives as 16 June 2026.
- Confirm ISO 13485:2016 clause numbers against the standard (R16 to R18).
- Confirm IEC 82304-1 complaint content (R19) against the standard.
- SaMD classification (for example, MDR Rule 11 and IEC 62304 safety class) was not researched. It drives which of the above applies to each software release.

---

## 3. Recommended form field lists

Conventions: "Req" is required at submission. "End user" means the form shown to clinicians, patients and carers. QMS-only fields are marked **[QMS]** and are hidden from end users. Field counts are under 25 for each kind.

### 3.1 Feedback (end-user friendly; 12 fields)

Feedback is any input that is not a complaint, for example a usability suggestion or a question. A feedback item can be promoted to a complaint by QMS staff, or by the "affected care" question below.

| # | Field | Type | Req | Help text (end user) | Satisfies |
|---|---|---|---|---|---|
| 1 | Feedback type | Select: question, suggestion, praise, usability issue, something went wrong | Yes | Choose the closest option. | R16 (feedback record), classification |
| 2 | Summary | Text, max 120 | Yes | One sentence describing your feedback. | R16 |
| 3 | Details | Long text | No | Tell us more. Do not include patient names. | R16 |
| 4 | Product | Select from device list | Yes | Which product or app is this about? | R1 (device identification) |
| 5 | Software version | Text, auto-filled from app "About" screen where possible | No | Found under Settings > About. | R1, R19 |
| 6 | Date you noticed this | Date | No | Approximate date is fine. | R1 (date of event) |
| 7 | I am a | Select: clinician, patient, carer, distributor, other | Yes | Helps us follow up in the right way. | R1 (reporter type) |
| 8 | Country | Select | Yes | Where you are using the product. | R14 (routing) |
| 9 | Contact email | Email | No | Only if you want a reply. | Reporter traceability |
| 10 | OK to contact me | Checkbox | Req if 9 given | We will contact you only about this feedback. | Consent record |
| 11 | Did this affect patient care or safety? | Select: No, Yes, Not sure | Yes | If Yes or Not sure, we will also treat this as a complaint. | Routing to complaint path (R1) |
| 12 | Attachment | File, optional, max 10 MB | No | Screenshots help. Remove personal information first. | Evidence |

**[QMS] fields for feedback:** triage decision (feedback / complaint / not actionable), assigned owner, complaint ID if promoted, date triaged. These are not shown to end users.

### 3.2 Complaint (QMS staff and reporter; 22 fields)

A complaint is any written, electronic or oral communication alleging deficiency in identity, quality, durability, reliability, safety, effectiveness or performance of a device, after release. Each complaint needs a reportability decision (R17, R18).

| # | Field | Type | Req | Help text | Satisfies |
|---|---|---|---|---|---|
| 1 | Complaint ID | Auto | Yes | System generated. | R17 traceability |
| 2 | Received date and time | Auto timestamp | Yes | Set at first receipt, not at triage. | R17 intake control |
| 3 | Intake channel | Select: portal, email, phone, sales or service rep, distributor, Yellow Card, other | Yes | How the complaint arrived. | R17 (channel control) |
| 4 | Reporter type | Select: clinician, patient, carer, distributor, internal, other | Yes | | R1, R17 |
| 5 | Reporter name and organisation | Text | Yes (non-anonymous) | Name may be withheld on request, but record the contact. | R17 traceability |
| 6 | Reporter contact | Email or phone | Yes (non-anonymous) | | R17 |
| 7 | Country of use | Select | Yes | | R14 routing |
| 8 | Patient reference | Pseudonymous ID, age range, sex | No | Do not record patient name. | R1, R2 |
| 9 | Device name | Select from device master | Yes | | R1 |
| 10 | UDI-DI and UDI-PI or lot / serial | Text, validated | Yes if known | Found on device label or app. | R1 |
| 11 | Software version and build | Text | Yes | | R1, R19 |
| 12 | Configuration and environment | Text (OS, integrations, hardware) | No | | R19, R20 |
| 13 | Date of event | Date | Yes | | R1 |
| 14 | Description of event | Long text | Yes | What happened, what was expected, what was done. | R1, R20 |
| 15 | Event type | Select: malfunction, wrong output, no output, data loss or corruption, usability, labelling or IFU, cybersecurity, other | Yes | | R20 (device problem code), R22 |
| 16 | Patient or user outcome | Select: none, minor, injury, serious injury or deterioration, death, unknown | Yes | | R1, R2, R22 |
| 17 | Immediate action taken | Text | No | | R5 |
| 18 | Ongoing risk to others | Select: no, yes, unknown | Yes | | R1, R3 |
| 19 | Attachments | File | No | | Evidence |
| 20 | **[QMS]** Reportability decision | Select: reportable serious incident, reportable other, not reportable, pending | Yes before closure | Record the rationale. | R17, R18 |
| 21 | **[QMS]** Decision rationale, approver, date | Text, user, date | Yes if 20 set | | R17 documented decision |
| 22 | **[QMS]** Linked records | IDs: vigilance report, CAPA, risk file, investigation | No | | R9, R17 |

### 3.3 Vigilance report (suspected incident, malfunction, adverse event; 22 fields)

This form starts a regulatory clock. Awareness date (field 3) and the reportability decision drive the deadline calculation. Deadlines are shown for the team to verify (R1 to R3, R22).

| # | Field | Type | Req | Help text | Satisfies |
|---|---|---|---|---|---|
| 1 | Report type | Select: suspected serious incident, malfunction, near miss, trend, FSCA | Yes | | R1, R5, R7, R13 |
| 2 | Source complaint or feedback ID | Link | Yes | | R17 traceability |
| 3 | Date of awareness | Date and time | Yes | Date the manufacturer first became aware. Drives the deadline. | R1 to R3 (clock start), R22 (awareness) |
| 4 | Date of event | Date | Yes | | R1 |
| 5 | Country where event occurred | Select | Yes | | R14, R12 |
| 6 | Device, UDI-DI, UDI-PI or lot / serial | Text, validated | Yes | | R1 |
| 7 | Software version and build, install date | Text, date | Yes | | R1, R19 |
| 8 | Event description and timeline | Long text | Yes | | R1, R20 |
| 9 | Patient outcome | Select: death, serious deterioration, serious public health threat, injury, no harm, unknown | Yes | | R1 to R3 |
| 10 | Patient demographics | Age range, sex (no identifiers) | No | | R1, R2 |
| 11 | Device problem code | IMDRF Annex A code (picklist) | Yes | | R20 |
| 12 | Health effect code | IMDRF Annex E and F codes (picklist) | Yes if harm | | R20 |
| 13 | Component code | IMDRF Annex G (picklist) | No | | R20 |
| 14 | Causal relationship | Select: established, reasonably possible, not established, unknown | Yes | Triggers the immediate-report duty. | R1 (trigger) |
| 15 | Remedial action or FSCA taken | Select plus text | Yes | | R5, R6 |
| 16 | Other devices or products involved | Text | No | | R1 |
| 17 | Reporter identity and role | Name, organisation, role | Yes | Held in confidence; regulator copy may need redaction. | R1, R12 |
| 18 | Report version | Select: initial, follow-up, final | Yes | Initial may be incomplete where needed to meet the deadline. | R4 |
| 19 | Submitted to | Select: MORE (GB or NI), EUDAMED, FDA MedWatch, other | Yes on submission | | R12, R14, R22 |
| 20 | Regulator reference and submission date | Text, date | Yes on submission | | R1 (audit trail) |
| 21 | Calculated deadline | Auto: awareness plus 2, 10 or 15 days, per rule | Auto | Calculated, not a legal opinion. Check against the applicable regulation. | R1 to R3 [V] |
| 22 | Investigation and CAPA links, final report date | Links, date | Yes before closure | | R9, R18 |

---

## 4. Design notes for the build

- Keep end-user intake to 12 fields. Hide all **[QMS]** fields. Route "affected care" answers to the complaint path automatically.
- Store the complaint reporter in a separate contact record, so one reporter can link to many complaints (Veeva model).
- Do not store patient names. Use pseudonymous references only.
- Store the awareness timestamp as an immutable audit field. It starts the clock.
- Add a reportability decision with approver and rationale before a complaint can close (ISO 13485 clause 8.2.2 [S]).
- Reporter identity controls (2FA or SSO) are not confirmed as a competitor norm. Decide on policy separately; for anonymous or patient reporters, a magic-link email is a lighter option than SSO.
- Keep IMDRF codes as picklists, versioned by annex edition, so the Edition 4 mapping can be updated.
