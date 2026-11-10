# ISO 13485:2016 clauses 4–8: application coverage matrix

Standard: BS EN ISO 13485:2016+A11:2021 (annotated copy supplied by the user).
Reviewed at commit `af25ec8` on branch `claude/classification-per-framework`.

## Scope and method

ISO 13485 governs the organisation, not the software. This matrix asks a narrower question for
each normative requirement in clauses 4 to 8: does the eQMS application provide the capability
that the organisation needs in order to meet it, and where is that capability missing?

- **Supported:** the application provides the capability, with code evidence.
- **Partial:** part of the requirement is provided. The gap is described.
- **Not covered:** no capability in the application. The organisation must use a procedure or
  another tool.
- **Organisational:** a policy, governance or physical matter that software cannot satisfy.
  Listed for completeness.

Evidence comes from reading the code, models, README and help pages. The test suite was not run
for this review. Items marked **To verify** need a check before the matrix is relied on.

File references are relative to the repository root.

---

## Clause 4: Quality management system

| Clause | Requirement (summary) | Status | Evidence | Notes / gap |
|---|---|---|---|---|
| 4.1.1 | Document the QMS and maintain its effectiveness; determine processes, sequence and interaction; monitor them; keep records | Partial | `README.md` (module table); `qms/models/documents.py` (Document); `qms/services.py` (process services) | Process map and interaction description are organisational documents. The app stores them as documents but does not model the processes. |
| 4.1.2 | Document the roles the organisation undertakes (manufacturer, authorised representative, importer, distributor) | Supported | `qms/models/organisation.py` (`OPERATOR_ROLES`, `join_operator_roles`); `qms/models/devices.py` (per-device operator roles) | Recorded per device and per organisation profile. |
| 4.1.3 | Outsourced processes: monitor, ensure control, retain responsibility, written quality agreements | Partial | `qms/models/suppliers.py` (Supplier, SoupItem); supplier evaluation and re-evaluation fields | Quality agreements are not modelled as records. Outsourced-process monitoring is a supplier record, not a process monitor. |
| 4.1.6 | Document and validate software used in the QMS, before first use and after change | Supported | `README.md` (Validation support, Release identification); `qms/validation.py` (`automated_test_ids`); `run_oq` management command; `qms/test_release.py` | The application is itself to be validated by the user (stated in `README.md`). It supplies the OQ evidence mechanism. |
| 4.2.1 | QMS documentation includes quality policy, objectives, quality manual, procedures, records | Partial | `qms/models/documents.py` (`DOC_TYPES`) | The quality policy and objectives are not a distinct record type. Stored as documents only if the user creates them. |
| 4.2.2 | Quality manual: scope and exclusions, procedures or references, process interaction, structure | Partial | As 4.2.1 | Stored as a document. The app does not enforce the required content. |
| 4.2.3 | Medical device file per device type or family | Supported | `qms/models/devices.py` (Device, `TechnicalFileBuild`); `qms/techfile.py` (`_effective_docs`, `_version_approvals`) | Technical file build assembles documents, registers and a checksummed manifest. Completeness check lists gaps. |
| 4.2.4 | Document control: review and approve before issue; re-approve; revision status; versions at point of use; legibility; external documents; prevent unintended use of obsolete documents | Partial | `qms/models/documents.py` (`DocumentVersion`, status, `obsolete`, `next_review_date`); `qms/services.py:79` (independent approval); `qms/help/documents.md` | Covered: approval, revision, superseded and obsolete status, periodic review. Not covered: external-origin documents (no register or distribution control); point-of-use availability; a defined retention period for obsolete copies. |
| 4.2.4 (retention of obsolete documents) | Retain at least one copy of obsolete documents for the defined period | Partial | `obsolete_on` set on withdrawal (`qms/services.py` obsolete_document); `qms/retention.py`; `retention_report` command | Withdrawn documents are locked, never deleted, and their retention end date is computed from the device lifetime (or the longest active lifetime for QMS-wide documents). Documents withdrawn before this change have no date. |
| 4.2.5 | Records: controls for identification, storage, security, integrity, retrieval, retention time and disposition; protect confidential health information; legible and changes identifiable; retain for device lifetime, at least two years | Partial | `qms/models/core.py:149` (`verify_audit_chain`); `qms/models/core.py:172` (`AuditedModel`); `qms/models/core.py:236` (`Record`); `qms/models/core.py:253` (no-patient-data confirmation); `qms/retention.py`; `expected_lifetime_years` on Device; `retention_report` command | Strong: append-only audit trail, hash chain, immutable records, changes identifiable. Retention period is now computed per record (longer of device lifetime and two years) and reported. Disposition is still a manual decision, and nothing is deleted. |

---

## Clause 5: Management responsibility

| Clause | Requirement (summary) | Status | Evidence | Notes / gap |
|---|---|---|---|---|
| 5.1 | Top management commitment: communicate importance, quality policy, objectives, management review, resources | Organisational | — | Governance matter. Not a software function. |
| 5.2 | Customer focus: determine and meet customer and regulatory requirements | Partial | `qms/models/core.py` (Complaint, feedback sources) | Requirements capture is in documents and Change Requests. No customer requirements register. |
| 5.3 | Quality policy: established, communicated, reviewed | Partial | As 4.2.1 | Stored as a document. Review is a periodic-review date only. |
| 5.4.1 | Measurable quality objectives at relevant levels | Not covered | — | No objectives register or measurement against objectives. |
| 5.4.2 | QMS planning and maintaining integrity during change | Not covered | — | No QMS plan record. Change Requests cover individual changes. |
| 5.5.1 | Responsibilities and authorities defined, documented, communicated; interrelation of personnel | Supported | `qms/roles.py`; `qms/workflow.py:18-27` (roles); `qms/models/devices.py` (`DeviceMembership`); `README.md` (Device teams and roles) | Roles are per device and enforced in pages, forms, business rules and emails. |
| 5.5.2 | Management representative appointed | Partial | Role `QA` and `All-device access` in `qms/workflow.py` | The appointment is not recorded as a distinct record. |
| 5.5.3 | Internal communication processes | Partial | `qms/notifications.py`; `README.md` (Notifications) | Email and digest exist. No communication plan record. |
| 5.6.1 | Management review: documented procedure, planned intervals, records | Partial | `qms/models/core.py` (Management Review record type, `wf.MANAGEMENT_REVIEW`); `qms/workflow.py` (planned → held → closed, QA signature) | The review is recorded per device. The planned-interval procedure is a document. Reviews across devices need one record per device. |
| 5.6.2 | Review inputs: feedback, complaint handling, reporting, audits, monitoring, corrective and preventive action, changes, recommendations, regulatory changes | Partial | `review_inputs` field (Management Review); `qms/workflow.py` (`MANAGEMENT_REVIEW` hold step requires it) | Inputs are recorded as text, checked for presence but not for completeness. The inputs themselves are the other records. |
| 5.6.3 | Review outputs: decisions and actions, resource needs | Supported | `resolution` and `resource_needs` fields (Management Review); close step requires both | Recorded and signed by QA. |

---

## Clause 6: Resource management

| Clause | Requirement (summary) | Status | Evidence | Notes / gap |
|---|---|---|---|---|
| 6.1 | Determine and provide resources | Organisational | — | Resource planning is outside the software. |
| 6.2 | Competence: determine necessary competence; training; evaluate effectiveness; awareness; records | Partial | `qms/models/documents.py:170` (`TrainingRequirement`); `qms/models/documents.py:186` (`TrainingAssignment`); `README.md` (Training, training matrix) | Strong on training assignment and sign-off. Gaps: no competence profile per role; no effectiveness evaluation of training; no education, skills or experience records. |
| 6.3 | Infrastructure: documented requirements, maintenance intervals and records | Not covered | — | No infrastructure or maintenance record. Likely out of scope for software-only devices. |
| 6.4 | Work environment and contamination control | Organisational | — | Physical environment. Out of scope for software. |

---

## Clause 7: Product realisation

| Clause | Requirement (summary) | Status | Evidence | Notes / gap |
|---|---|---|---|---|
| 7.1 | Plan product realisation: quality objectives, verification and validation, traceability, acceptance criteria, records | Partial | `qms/services.py:176` (`DEFAULT_PMS_SCHEDULES`); `qms/models/core.py` (PMSSchedule) | PMS schedule exists. No product realisation plan record. |
| 7.1 (risk) | Process for risk management in product realisation | Supported | `qms/models/risk.py` (Hazard, RiskControl); `README.md` (Risk management, ISO 14971) | Hazard register with before and after control scoring, acceptance and benefit-risk rationale. |
| 7.2.1 | Determine product requirements: customer, intended use, regulatory, user training, own requirements | Partial | `qms/models/devices.py` (regulatory particulars, intended purpose, intended users) | Intended use is recorded. User training requirements are not a record type. |
| 7.2.2 | Review of requirements before commitment to supply; records | Not covered | — | No contract or order review. Likely out of scope for software-only or own-brand devices. |
| 7.2.3 | Communication with customers, regulators, feedback, advisory notices | Partial | `qms/models/core.py` (Complaint); `README.md` | Advisory notices are not a record type. |
| 7.3.1–7.3.2 | Design and development procedure and planning: stages, reviews, verification and validation, responsibilities, traceability, resources | Partial | `qms/models/core.py` (Change Request); `qms/validation.py`; `qms/techfile.py` | Change Requests and requirement-to-test traceability are present. No design and development plan record and no stage-gate reviews. |
| 7.3.3 | Design inputs: functional, performance, usability and safety requirements; regulatory requirements; risk output; reviewed and approved | Supported | `qms/workflow.py` (`DESIGN_CONTROL`, `design_element` = input; submit requires acceptance criteria; QA approval with independent signature) | Inputs are records with a signed approval. Completeness of the requirement set is a review judgement. |
| 7.3.4 | Design outputs: meet inputs; acceptance criteria; essential characteristics; approved before release | Supported | `acceptance_criteria` required before submit (Design Control, output); signed approval before closure | Outputs must reference the input records in the text. The link is not enforced. |
| 7.3.5 | Design review at suitable stages, with participants and date | Supported | `attendees` and `planned_date` required for design reviews (`_design_review_complete` check) | Review date and participants are enforced. Stage planning is in the design plan, which is not modelled. |
| 7.3.6 | Design verification: plan, methods, acceptance criteria; records | Partial | `qms/validation.py` (`automated_test_ids`); `run_oq` | Covers software verification by automated test. Design verification plans for non-software outputs are not modelled. |
| 7.3.7 | Design validation: plan, representative product, clinical or performance evaluation, records | Partial | `qms/validation.py`; `README.md` (Validation support) | Software validation only. Clinical evaluation is not modelled. |
| 7.3.8 | Design transfer to manufacturing | Not covered | — | No transfer record. Likely out of scope for software. |
| 7.3.9 | Design and development changes: significance, review, verification, validation, approval; records | Supported | `qms/models/core.py` (Change Request workflow); `qms/workflow.py` (`CHANGE_REQUEST`); `qms/models/risk.py` (risk controls linked to Change Requests) | Strong: change workflow with review and approval, linked to risk. |
| 7.3.10 | Design and development file per device type or family | Partial | `qms/models/devices.py` (Device, technical file); `qms/techfile.py` | Technical file build covers the documentation. No design file index separate from the technical file. |
| 7.4.1 | Purchasing process: procedures; supplier selection criteria; monitoring and re-evaluation; records | Supported | `qms/models/suppliers.py:10` (Supplier, signed evaluations, re-evaluation dates); `README.md` (Suppliers and SOUP) | Criteria are recorded as evaluations. Monitoring performance inputs are not structured. |
| 7.4.2 | Purchasing information: specifications, requirements, supplier notification of changes; traceability | Partial | `qms/models/suppliers.py` | Free-text supplier information. No structured purchasing information record. |
| 7.4.3 | Verification of purchased product | Not covered | — | No inspection record for purchased product. |
| 7.5.1 | Production control: procedures, qualification of infrastructure, process monitoring, labelling, release; record per device or batch with amount manufactured and approved | Not covered | — | No production record or batch record. Likely out of scope for software-only devices. |
| 7.5.2 | Cleanliness of product | Organisational | — | Physical product. Out of scope. |
| 7.5.3–7.5.5 | Installation, servicing, sterile device requirements; sterilisation parameters per batch | Not covered | `qms/models/devices.py` (sterile classification, `Is`) | Classification recorded for sterile devices. No sterilisation or installation records. Out of scope for software-only devices. |
| 7.5.6 | Validation of production and service processes; software used in production validated | Partial | `qms/validation.py`; `README.md` (Validation support) | Software validation is covered. Process validation records are not. |
| 7.5.7 | Sterilisation and sterile barrier validation | Not covered | — | Out of scope for software-only devices. |
| 7.5.8 | Identification of product, status, UDI where required, returned product | Partial | `qms/models/core.py:228` (`software_version`, `software_item`) | Software identity is recorded. No UDI or device identifier field. No returned-product identification. |
| 7.5.9 | Traceability procedures and records | Partial | `qms/models/core.py:409` (`RecordLink`); `qms/models/devices.py` (software items) | Links between records and software items are traceable. No batch, lot or serial traceability. |
| 7.5.10 | Customer property | Organisational | — | Out of scope for software. |
| 7.5.11 | Preservation of product | Organisational | — | Physical packaging and storage. Out of scope for software. |
| 7.6 | Calibration and control of monitoring and measuring equipment; validation of measurement software; records | Not covered | — | No equipment register or calibration records. Measurement software validation is covered by 4.1.6. |

---

## Clause 8: Measurement, analysis and improvement

| Clause | Requirement (summary) | Status | Evidence | Notes / gap |
|---|---|---|---|---|
| 8.2.1 | Feedback: gather and monitor customer information; documented procedure; post-production data; input to risk management | Partial | `qms/services.py:181-190` (complaint trend review, clinical feedback round); `qms/models/core.py:240` (source field, incl. user feedback) | Feedback is captured through Complaints and PMS activities. The feedback procedure is a document. No feedback data register. |
| 8.2.2 | Complaint handling: receive and record; evaluate; investigate; reporting decision; handling of product; corrective action; justification if not investigated | Supported | `qms/workflow.py` (`COMPLAINT`); `qms/models/core.py:280` (reportable field); `qms/models/core.py:285` (vigilance deadlines); `qms/workflow.py:175` (CAPA link) | Justification for not investigating is not enforced by a required field. To verify. |
| 8.2.3 | Reporting to regulatory authorities: procedure for notification; records | Supported | `qms/models/core.py:280-285`; `qms/settings.py:183-187` (`QMS_VIGILANCE_DEADLINES`) | Reportable decision and deadlines per category. The submission itself is made outside the application. |
| 8.2.4 | Internal audit: programme at planned intervals; procedure; objectivity; auditors do not audit their own work; records; follow-up | Partial | `qms/workflow.py` (`INTERNAL_AUDIT`, `_auditor_independent`: lead auditor ≠ auditee; QA signed close with independent sign-off) | Audit records, independence and sign-off are enforced. The audit programme (planned intervals and scope selection) and the follow-up of each finding through CAPA are not modelled. |
| 8.2.5 | Monitoring and measurement of QMS processes; corrective action when planned results are not met | Partial | `qms/services.py:176-190` (PMS schedules and reviews) | Process monitoring is by scheduled activities only. No process performance measures. |
| 8.2.6 | Monitoring and measurement of product; release not proceeding until complete; identity of releasing person | Partial | `qms/workflow.py` (release steps with signatures); `qms/models/core.py` (`Signature`) | Signed release steps exist for records. No product inspection or test plan record. |
| 8.3.1 | Nonconforming product: identify, control, document, evaluate, dispose; procedure; records | Supported | `qms/workflow.py` (`NONCONFORMANCE`: open → evaluation → disposition → verification → closed); `nc_disposition` field | Identification of product status and segregation are physical processes outside the software. |
| 8.3.2 | Actions before delivery: correction, preclusion, concession with justification, approval, regulatory check | Supported | `nc_disposition` (rework, use as is under concession, scrap, return to supplier); `_concession_justified` check (justification and risk file checked); QA signature on disposition | The regulatory check is confirmed through the risk file. Whether a notification to the regulator is needed is still a judgement recorded in the text. |
| 8.3.3 | Actions after delivery, advisory notices, procedure capable of immediate effect | Partial | `qms/workflow.py` (Incident, Complaint); `qms/models/core.py:280` | No advisory notice record type. |
| 8.3.4 | Rework procedure, verification after rework, records | Supported | `nc_disposition` = rework, followed by the Verify disposition step (verification evidence required) | Rework procedure document is the user's. |
| 8.4 | Analysis of data: procedure; statistical methods; inputs from feedback, conformity, trends, suppliers, audits, service reports | Partial | `qms/services.py:181-182` (trend review by severity, software item and site); `qms/models/suppliers.py` | Trend review exists as a scheduled activity. No statistical analysis and no supplier or audit data feed. |
| 8.5.1 | Improvement: changes to ensure suitability, adequacy and effectiveness | Partial | `qms/workflow.py` (CAPA, Change Request); `qms/models/core.py` | Improvement is driven by CAPA and Change Request records. No improvement plan. |
| 8.5.2 | Corrective action: eliminate causes; procedure covering review, root cause, evaluation, action, verification, effectiveness | Supported | `qms/workflow.py:175-190` (CAPA states: open, root cause, action plan, implementing, effectiveness check, closed; effectiveness-check transition) | Strong. The effectiveness check must pass before close (`workflow.py:184-190`). |
| 8.5.3 | Preventive action: determine potential nonconformities, evaluate, plan, verify, review effectiveness | Partial | `qms/workflow.py:175` (CAPA) | The CAPA record type is not labelled for preventive action. Confirm whether CAPA is used for both. **To verify.** |

---

## Summary

- **Strongest areas:** document control (4.2.4), records and audit trail (4.2.5), device technical file (4.2.3), roles (5.5.1), training assignment (6.2), supplier control (7.4.1), change control (7.3.9), risk (ISO 14971), complaint handling and vigilance reporting (8.2.2, 8.2.3), and corrective action with effectiveness check (8.5.2).
- **Implemented in this change:** management review (5.6), internal audit records with independence (8.2.4), nonconforming product with concession and disposition (8.3), design input, output and review records (7.3.3 to 7.3.5), retention periods and the retention report (4.2.4, 4.2.5).
- **Remaining gaps:**
  1. Internal audit programme: planned intervals and scope selection (8.2.4).
  2. Link audit findings and management-review actions to CAPA automatically (8.2.4, 5.6.3).
  3. Design and development plan and verification/validation plans (7.3.2, 7.3.6, 7.3.7).
  4. Retention disposition as a recorded decision, and retention for documents withdrawn before this change (4.2.5).
  5. Competence records and training effectiveness evaluation (6.2).
  6. Purchased-product inspection records (7.4.3) and advisory notices (8.3.3).
- **Likely out of scope for a software-only device:** infrastructure (6.3), work environment (6.4), production and batch records (7.5), sterilisation (7.5.5, 7.5.7), installation and servicing (7.5.3, 7.5.4), product preservation (7.5.11), calibration (7.6). Confirm against the device's actual scope.
- **To verify before relying on this matrix:** whether the complaint "not investigated" justification is enforced (8.2.2); whether CAPA covers preventive action (8.5.3); whether the test suite passes on this commit.
