# SAMD_QMS

[![CI](https://github.com/tartarini/eQMS/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/tartarini/eQMS/actions/workflows/ci.yml?query=branch%3Amain)
[![Tests](https://raw.githubusercontent.com/tartarini/eQMS/badges/tests.svg)](https://github.com/tartarini/eQMS/actions/workflows/ci.yml?query=branch%3Amain)
[![Coverage](https://raw.githubusercontent.com/tartarini/eQMS/badges/coverage.svg)](https://github.com/tartarini/eQMS/actions/workflows/ci.yml?query=branch%3Amain)
[![OQ](https://raw.githubusercontent.com/tartarini/eQMS/badges/oq.svg)](docs/developer-guide.md#validation)
![Python 3.13](https://img.shields.io/badge/python-3.13-3776ab?logo=python&logoColor=white)
![Django 5.2](https://img.shields.io/badge/django-5.2-092e20?logo=django&logoColor=white)
![PostgreSQL 16](https://img.shields.io/badge/postgresql-16-4169e1?logo=postgresql&logoColor=white)

A quality management system for organisations that make software as a medical device (SaMD),
written in Django. One installation manages the QMS for any number of devices.
It enforces the process rather than just recording it: workflows, roles, electronic signatures,
traceability and a tamper-evident audit trail across every module.

It is a tool to support your QMS. It is not itself validated: before using it for regulated
records you must validate it (ISO 13485 §4.1.6 software validation) and check it against your SOPs.

## Documentation

- **Developer guide:** [docs/developer-guide.md](docs/developer-guide.md): architecture,
  invariants, data model, workflow engine, audit trail, signatures, SSO, settings, testing,
  common changes, deployment and validation.
- **User help:** built in, at `/help/` (source in `qms/help/`). Every page has a **Help** link to
  the section about that page, and every form field has a **?** icon explaining what to enter.
  It ships with each release, so it always matches the version in use.

## Modules

| Module | What it does | Standard |
| --- | --- | --- |
| Device teams and roles | People are on one or more device teams with **roles per device** (Engineer, QA, Clinical Safety Officer, Device admin), so someone can be QA on one device and an Engineer on another. They only see and act on their devices; an All-device access role covers heads of quality and auditors. Enforced in pages, forms, business rules, emails and training | ISO 13485 §4.2.5, §6.2 |
| Landing page and account requests | A public home page explains the platform. Anyone can **request an account**: they pass a captcha (self-hosted proof of work, or Cloudflare Turnstile), register with Google, Microsoft, LinkedIn or ORCID single sign-on, then describe who they are and what they need. Emails not verified by the provider (ORCID) are confirmed by link. Device admins and QA approve onto a team they manage; QA can decline with a reason. A request alone gives no access | ISO 13485 §6.2 |
| Invitations | Device admins and QA invite people by email, with roles on each device they manage. The link is single use, expires (14 days by default), works only for the invited address, and can be resent or revoked. New people create an account or use single sign-on | ISO 13485 §6.2 |
| Validation support | User requirements traced to automated tests; `run_oq` writes signed-off-ready OQ evidence for the validation plan | ISO 13485 §4.1.6 |
| Devices | Manage any number of medical devices. Each has its own regulatory particulars, software items, quality records, risk file, PMS schedule, SOUP list and technical file; QMS-wide procedures and training are shared. A header switcher focuses every page on one device | ISO 13485 §4.2.3 |
| Technical file | One click builds a device's technical documentation (MDR Annex II/III structure) from live QMS data: Word and HTML documents, CSV registers, every effective document file, and a checksummed manifest, in a frozen ZIP. A completeness check lists gaps; QA approves a build with a signature | EU MDR Annex II, III; UK MDR |
| Quality records | Problem Reports, Complaints, Incidents, CAPAs, Change Requests and PMS Activities, each with an enforced workflow, required fields, role gates and typed links | IEC 62304 §6, §8, §9; ISO 13485 §8.2, §8.5 |
| Document control | Numbered documents (SOP-001…) with versions: draft → in review → approved (signed, by someone other than the author) → effective. A new effective version supersedes the old one. Files are frozen after submission and checksummed; approval refuses a file that changed. Periodic review dates, signed "no change" reviews, signed withdrawal | ISO 13485 §4.2.4 |
| Training | Training requirements per document and role. When a version becomes effective, everyone in those roles is assigned it; they sign "read and understood". New joiners are picked up daily. Training matrix | ISO 13485 §6.2 |
| Risk management | Hazard register (HAZ-001…) with hazard, sequence of events, hazardous situation, harm, 5×5 severity × probability before and after controls, risk controls linked to the Change Request that implements them, and signed acceptance. Acceptance is blocked until residual risk is scored, all controls are verified, and any residual risk above "acceptable" has a benefit-risk rationale. Records link to hazards | ISO 14971 |
| Suppliers and SOUP | Approved supplier list with signed evaluations and re-evaluation dates; SOUP list with versions, safety class and anomaly-review dates | ISO 13485 §7.4; IEC 62304 §8.1.2 |
| Attachments | Evidence files on records: type and size limits, a no-patient-data confirmation, SHA-256 on upload, checked again on download, never changed or deleted | — |
| Notifications | Email for new incidents (QA and Clinical Safety, immediately), complaints, assignments, steps awaiting a role, documents for review, training; a daily digest of overdue and due-soon items | — |
| Single sign-on | Google, Microsoft, LinkedIn, ORCID and GitHub, alongside local accounts | — |
| Help | Built-in help for every page and a ? icon on every form field, versioned with the release | — |
| Release identification | Every page (including sign-in, help and admin) shows the version and source commit at the top and the copyright notice at the foot; `/healthz` and the OQ report carry the same commit | ISO 13485 §4.1.6 |
| Audit and security | Every create, change, status change, signature, link, upload, login, failed login, role change and SSO connection is logged, append-only and SHA-256 hash-chained. Nothing is deleted | 21 CFR Part 11-style controls |

## Electronic signatures

Approvals ask you to re-enter your password. The signature stores who, when, what it means
(e.g. "Document approval", "Risk acceptance") and a hash of the exact state signed.
Single sign-on users have no local password, so they set a **signing PIN** (Signing PIN in the
top bar) within 15 minutes of signing in; anyone can set one instead of using their password.

## Quick start

With Docker (recommended; same image as production, PostgreSQL and a mail catcher):

```bash
make dev        # http://localhost:8000 · emails at http://localhost:8025
make demo       # demo devices and users
make test
```

Without Docker (SQLite):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py load_demo_data
python manage.py runserver
```

Sign in as `engineer`, `qa`, `qa2` or `cso` (password `demo-pass-123`). Roles are per device:
`engineer` is an Engineer on SkinCheck but Engineer, QA and Device admin on RespiTrack; `qa` is the
head of quality (QA organisation-wide, with All-device access); `qa2` (QA) and `cso` (Clinical
Safety Officer) are on SkinCheck only.

For a clean install use `seed_qms` instead of `load_demo_data`, create a superuser, and give
your head of quality an account with the QA group and `All-device access` in Admin. They add the
devices (becoming QA and Device admin on each) and **invite** everyone else from each device's
page, choosing their roles on that device.

Run the tests: `python manage.py test qms` (156 tests). For validation evidence:
`python manage.py run_oq --executed-by "Your Name" --release 1.0.0`.

## Deployment

Production runs on a single Linux server with Docker Compose (Caddy for HTTPS, gunicorn,
a scheduler for daily jobs and backups, PostgreSQL 16), provisioned and deployed with Ansible;
CI builds, tests and publishes the image. See **[docs/deployment.md](docs/deployment.md)**.

```bash
make provision ENV=production
make deploy ENV=production VERSION=1.0.0
make restore-test ENV=production
```

## Single sign-on

Each provider is switched on by setting its credentials as environment variables, then shown as
a "Continue with…" button on the sign-in page. Register the app with the provider and use these
redirect (callback) URLs, replacing the host with yours:

| Provider | Environment variables | Redirect URL |
| --- | --- | --- |
| Google | `SSO_GOOGLE_CLIENT_ID`, `SSO_GOOGLE_SECRET` | `https://HOST/accounts/google/login/callback/` |
| Microsoft (Entra ID) | `SSO_MICROSOFT_CLIENT_ID`, `SSO_MICROSOFT_SECRET`, optional `SSO_MICROSOFT_TENANT` (default `organizations`; set your tenant ID to allow only your organisation) | `https://HOST/accounts/microsoft/login/callback/` |
| LinkedIn ("Sign In with LinkedIn using OpenID Connect" product) | `SSO_LINKEDIN_CLIENT_ID`, `SSO_LINKEDIN_SECRET` | `https://HOST/accounts/oidc/linkedin/login/callback/` |
| ORCID (public API) | `SSO_ORCID_CLIENT_ID`, `SSO_ORCID_SECRET`, optional `SSO_ORCID_DOMAIN=sandbox.orcid.org` for testing | `https://HOST/accounts/orcid/login/callback/` |
| GitHub | `SSO_GITHUB_CLIENT_ID`, `SSO_GITHUB_SECRET` | `https://HOST/accounts/github/login/callback/` |

New people can also **request an account** from the home page (`/request-access/`): after a
captcha they register with Google, Microsoft, LinkedIn or ORCID (`QMS_ACCESS_REQUEST_PROVIDERS`;
GitHub is for sign-in only), and their request waits under **Account requests** for a Device
admin or QA. The captcha is self-hosted by default (`QMS_CAPTCHA=pow`, no keys, no third party);
set `QMS_CAPTCHA=turnstile` with `QMS_TURNSTILE_SITE_KEY` and `QMS_TURNSTILE_SECRET_KEY` to use
Cloudflare Turnstile instead.

Because these are public identity providers, access is controlled separately:

- Signing in gives no access. A person needs a role on a device team; until then they see
  "Access pending", and QA is emailed. The usual route in is an invitation from a Device admin or
  QA, which can also create the account through single sign-on for the invited address.
- An SSO login joins an existing account when the provider confirms the email address is
  verified and it matches. So the safest set-up is: an admin creates the account with the
  person's email, and they sign in with SSO.
- New accounts are created automatically only for verified emails in
  `QMS_SSO_ALLOWED_DOMAINS` (e.g. `sheffield.ac.uk`). Leave it empty to allow only
  pre-created accounts.
- ORCID does not share email addresses, so it cannot create or match an account. Sign in another
  way, open **Connected accounts**, and connect your ORCID iD; after that it works for sign-in.
- Provider login starts with a POST (CSRF-protected), and no provider tokens are stored.

## Scheduled jobs

Run daily (cron, systemd timer or your platform's scheduler):

```bash
python manage.py generate_pms_activities   # create PMS tasks 30 days before they're due
python manage.py send_reminders            # assign missing training, email overdue/due-soon digests
python manage.py verify_audit              # exits non-zero if the audit chain was tampered with
```

## Running it for real

- Environment: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`, `QMS_BASE_URL`
  (used in email links), `DJANGO_MEDIA_ROOT` (persistent, backed-up storage for files).
- Email: `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT`, `DJANGO_EMAIL_USER`, `DJANGO_EMAIL_PASSWORD`,
  `DJANGO_FROM_EMAIL`. Without them, emails are printed to the console.
- Use PostgreSQL rather than SQLite, serve over HTTPS only, and back up the database and media
  together. The hash chain shows tampering but cannot restore deleted data.
- Check `QMS_VIGILANCE_DEADLINES` and the risk thresholds (`QMS_RISK_ACCEPTABLE_MAX`,
  `QMS_RISK_UNACCEPTABLE_MIN`) in `config/settings.py` against current MHRA guidance and your
  risk management plan.
- Keep patient and participant data out: no names, NHS or hospital numbers, identifiable images
  or recordings.

## Layout

```
qms/workflow.py        record types, statuses and transition rules
qms/services.py        every status change, signature and rule check
qms/models/            core (records, audit, signatures, attachments), documents and training,
                       risk, suppliers
qms/notifications.py   emails and the daily digest
qms/sso.py, sso_settings.py   single sign-on rules and provider configuration
qms/signals.py         security events into the audit trail
```

## Copyright

Copyright 2026-2027 Daniele Tartarini. The notice appears at the foot of every page of the web
app and on the OQ evidence report.
