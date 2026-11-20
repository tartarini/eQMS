# Post-market surveillance (the `pms` app)

The `pms` app takes feedback, complaints and suspected incidents about a device from the people
who use it: QMS staff, clinicians, patients and carers. Each report gets a reference number
(`PMS-00001`) and is kept as a QMS record.

## Who can report, and how

- **Anyone who reports must be signed in.** Two ways in:
  - **Single sign-on** with the providers the QMS already uses (Google, Microsoft, LinkedIn, ORCID,
    GitHub), where the provider is configured.
  - **A local account.** New end users register at `/pms/register/` with a name, email, username,
    password and the kind of user they are (clinician, patient, carer or other). The account is
    inactive until they open the activation link sent to their email. The link expires after
    `QMS_PMS_ACTIVATION_DAYS` (2) and works once.
- **Two-factor sign-in is mandatory** on every `/pms/` page, and on every SAMD_QMS page in
  production (`QMS_TWO_FACTOR=1`, set by the production Ansible group; development, staging and
  the tests leave it off). The first time, the person sets up an
  authenticator app (any TOTP app) and enters a code. After that, each session needs a code,
  whether the person signed in with a password or with single sign-on. This is enforced by
  `pms.middleware.TwoFactorMiddleware`. Recovery codes are offered by allauth as a fallback.
- QMS staff use their existing accounts. Anyone with a QMS role can triage reports.

## Reports

| Kind | For | Required beyond the summary and description |
| --- | --- | --- |
| Feedback | Opinions and suggestions | Device |
| Complaint | Dissatisfaction with the device, its labelling or service | Device, what happened to the patient (harm) |
| Suspected incident or malfunction | Something that may be a vigilance matter | Device, date it happened, date the manufacturer became aware, harm |

For a suspected incident, the reporting clock runs from the date of awareness. The report shows the
latest dates for each period in `QMS_VIGILANCE_DEADLINES` (2, 10 and 15 days). Verify these periods
against current guidance before relying on them (see the research note).

Reporters see only their own reports. QMS staff see all reports and set the status
(new, triaged, under investigation, closed).

## Links to external issues

A reporter can link a report to an issue already raised in a bug tracker, by pasting its address
(`https://` only). GitHub, GitLab, Bitbucket and Jira links get a readable reference, such as
`acme/app#12`. Other https links are kept as given. The app does not call the tracker's API.

## Where the design comes from

[pms-reporting-requirements.md](pms-reporting-requirements.md) is the research note: the
competitor comparison, the regulatory matrix, and the field lists the forms are built from.

## Still to do

- Reportability decision (approver and rationale) before a complaint can close (ISO 13485 8.2.2).
- Verify the EU Art. 87 and UK vigilance periods against primary sources, and the SaMD
  classification of each release (not yet researched).
- Attachments (screenshots, logs) on reports.
- Link a report to a QMS complaint record.
- A phone-width and browser check of the surveillance pages.
