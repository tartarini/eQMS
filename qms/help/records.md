There are ten kinds of quality record. Each belongs to one device, moves through fixed statuses, and the next step only becomes available once the information it needs is filled in.

| Record | Use it for | Statuses |
| --- | --- | --- |
| Problem Report (PR) | Any software defect, wherever it was found | Open → Triage → Risk assessment → In fix → Verification → Released → Closed (or Rejected) |
| Complaint (CMP) | Feedback alleging a failure in safety, performance or usability | Received → Investigating → Reportability decision → Closed |
| Incident (INC) | A complaint or event that may be reportable to the MHRA | Assessing → Reported → Follow-up → Final report → Closed |
| CAPA | Root-cause fixes for systemic or repeated problems | Open → Root cause → Action plan → Implementing → Effectiveness check → Closed |
| Change Request (CR) | Any change to released software, including fixes | Proposed → Impact analysis → Approved → Implemented → Verified → Closed (or Rejected) |
| PMS Activity (PMS) | Scheduled post-market surveillance tasks, created automatically | To do → In progress → Review → Done |
| Internal Audit (IA) | Planned audits of QMS processes and documents, with the auditee and lead auditor kept separate (ISO 13485 8.2.4) | Planned → In progress → Report issued → Closed |
| Management Review (MR) | The top-management review of the QMS: inputs considered, decisions and resource needs (ISO 13485 5.6) | Planned → Held → Closed |
| Nonconforming Product (NC) | Product or software output that does not meet requirements, with its disposition and verification (ISO 13485 8.3) | Open → Evaluation → Disposition → Verification → Closed (or Rejected) |
| Design Control (DES) | A design input, design output or design review, approved before use (ISO 13485 7.3) | Draft → In review → Closed (approved) or Rejected |

## Working on a record

- **Create:** on the Dashboard, click **+ New** under the record type, and check the **Device** is right.
- **Edit:** open the record and click **Edit**. Every change is logged with your name.
- **Next steps:** the right-hand panel lists the steps available now. If a step is blocked, it lists why in red, such as a field to fill in, a role you need, or a link that's missing.
- **Owner:** set an owner to assign the record; they're emailed.
- **Locked:** once Closed, Rejected or Done, a record can't be changed.

## Linking records

Use **Traceability** on a record to link it to another by reference (for example CR-0003). Link types: *relates to*, *is fixed by*, *is caused by*, *escalated to*, *triggered*, *is verified by*. Some steps require a link:

- A Problem Report can't go to verification until it **is fixed by** a Change Request.
- A complaint judged reportable can't close until it is **escalated to** an Incident.

Use the **Hazards** field to link a record to entries in the device's risk register.

## Attachments

Add evidence such as logs, test reports and screenshots under **Attachments**. You must tick the box confirming the file has no patient or participant data. Files can't be changed or deleted after upload, and each download is checked against the file's original fingerprint.

## Report a software problem

1. Dashboard → **Problem Report** → **+ New**. Describe what happened, where (anonymised site ID) and the software version.
2. **Start triage**.
3. Fill in severity, patient-safety impact, software item and version, link any hazards, then **Move to risk assessment**.
4. Set **Risk file updated** to *Yes* or *Not needed* (not *Pending*), then **Start fix**.
5. Create a Change Request for the fix and link the Problem Report to it as **is fixed by**, then **Send to verification**.
6. Add the verification evidence (test run, pull request or report), then **Mark released**.
7. QA closes it with a signature. If it isn't a real defect, QA can **Reject** it from Open, Triage or Risk assessment, with a reason.

## Handle a complaint

1. Log it straight away as a **Complaint** and set **Date aware** to the day the organisation first heard of it. Record the reporter's role, never patient identifiers.
2. Set the source, then **Start investigation**.
3. Write the investigation summary, set patient-safety impact, then **Ready for reportability decision**.
4. QA or the Clinical Safety Officer sets **Reportable to MHRA** (*Yes* or *No*) with a rationale.
5. If *Yes*, create an Incident and link the complaint to it as **escalated to**. Then **Record decision and close** with a signature.
6. Link any Problem Report or CAPA the complaint triggered.

## Report an incident to the MHRA

1. Creating an Incident immediately emails QA and the Clinical Safety Officers on the device's team.
2. Set **Date aware** and the **Deadline category**. The record shows the **Report due** date, and the dashboard flags it in red once overdue.
3. Submit the report to the MHRA outside SAMD_QMS, then enter the **MHRA reference** and click **Record MHRA report** (QA or Clinical Safety Officer, signed).
4. **Start follow-up**, then **Final report submitted** once the investigation summary is complete.
5. QA closes it with a resolution and a signature.

Reporting deadlines in the system are a reminder only. Always check the current MHRA guidance for the timescale that applies.

## Run a CAPA

1. Create a CAPA and link the records that triggered it.
2. **Start root-cause analysis**, record the root cause, then **Plan actions**.
3. QA approves the plan with a signature (not the author).
4. Implement the actions. Add verification evidence and an **Effectiveness check due** date, then **Start effectiveness check**.
5. On the due date, QA either closes it as effective (signed, with the outcome and risk-file status) or sends it back to Implementing with a comment.

## Change released software

1. Create a Change Request describing the change and why, then **Start impact analysis**.
2. Fill in the software item, impact analysis (risk, requirements, tests, regression scope), affected hazards and risk-file status.
3. QA approves it with a signature. The author can't approve their own change. Don't start work before approval.
4. Put the reference (for example CR-0007) in your branch name and commit messages. **Mark implemented**, add verification evidence, then **Mark verified**.
5. QA closes it once the fix version is set.

## Complete a PMS activity

Post-market surveillance tasks are created automatically 30 days before they're due, from each device's PMS schedule. The standard schedule has monthly safety-notice and SOUP reviews; quarterly trend, real-world performance and subgroup reviews; six-monthly feedback and literature reviews; and the annual PMS report and plan review.

1. Open the activity and click **Start**.
2. Record what you reviewed and found under **Investigation summary / findings**. Raise and link any Problem Report, CAPA or Change Request.
3. **Submit for review**. QA either approves it with a signature or sends it back with a comment.

## Internal audits, management reviews and nonconforming product

- **Internal audit:** start only when the lead auditor (the record's owner) is different from the auditee. QA closes the audit with a signature from someone other than the person who created the record.
- **Management review:** QA records the review as held once the inputs are written down, then records the decisions and resource needs and closes it with a signature. The review is recorded against one device; for a multi-device organisation, record a review on each device or keep the QMS-wide minutes as a document.
- **Nonconforming product:** QA records the disposition with a signature from someone other than the person who created the record. A **use as is under concession** disposition needs a written justification and the risk file checked first. The disposition is then verified before the record closes.
- **Design control:** a design input or output is submitted for review with its acceptance criteria, and QA approves it with a signature from someone other than the person who created it. A design review also needs its participants and date. Approved design records are locked; a change to them goes through a Change Request.

## Retention

Nothing is deleted. Closed records and withdrawn documents must be kept for the device's expected lifetime (set on the device page) and never less than two years. The retention report lists when each item's retention period ends:

    python manage.py retention_report --within-days 90

If a device has no expected lifetime, the report marks its items so you can set it.

