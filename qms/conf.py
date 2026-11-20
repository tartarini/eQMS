"""Default values of every QMS_* setting.

The qms app reads these as ``settings.QMS_*``. ``QmsConfig.ready`` fills in any that the
project's settings do not define, so a project (the standalone ``config`` project, or a host
platform that installs SAMD_QMS as an app) only sets what it wants to change. Values that come
from the environment are read by the project's settings module, never here.

See "Settings reference" in docs/developer-guide.md.
"""
import copy

from . import __version__

DEFAULTS = {
    # --- Release identification -------------------------------------------------------
    # Label and commit shown at the top of every page, on /healthz and in the OQ report. The
    # project normally sets them from the container build (QMS_VERSION, QMS_COMMIT).
    "QMS_VERSION": __version__,
    "QMS_COMMIT": "unknown",
    # Shown at the foot of every page and every report the software produces.
    "QMS_COPYRIGHT": "Copyright 2026-2027 Daniele Tartarini",

    # --- Records ----------------------------------------------------------------------
    # Vigilance reporting deadlines, counted from "date aware".
    # VERIFY these against current MHRA guidance before relying on them.
    "QMS_VIGILANCE_DEADLINES": {
        "public_health_threat": {"label": "Serious public health threat", "days": 2},
        "death_or_serious_deterioration": {
            "label": "Death or unanticipated serious deterioration", "days": 10},
        "other_serious_incident": {"label": "Other serious incident", "days": 15},
    },
    # Approvals marked "independent" cannot be signed by the record's author.
    "QMS_REQUIRE_INDEPENDENT_APPROVAL": True,
    # generate_pms_activities creates activities this many days before they are due.
    "QMS_PMS_HORIZON_DAYS": 30,
    # Minimum retention of records and obsolete documents after closure or withdrawal (ISO
    # 13485 4.2.5). The retention period is the longer of this and the device's expected
    # lifetime.
    "QMS_RETENTION_MIN_YEARS": 2,

    # --- Post-market surveillance (pms app) and two-factor sign-in ---------------------
    # QMS_TWO_FACTOR: require an authenticator app on all of SAMD_QMS, not only /pms/.
    "QMS_TWO_FACTOR": False,
    "QMS_PMS_ACTIVATION_DAYS": 2,   # validity of the link that activates a new end-user account

    # --- Files ------------------------------------------------------------------------
    "QMS_ATTACHMENT_MAX_MB": 25,
    "QMS_ATTACHMENT_EXTENSIONS": [".pdf", ".docx", ".xlsx", ".csv", ".txt", ".md", ".png",
                                  ".jpg", ".jpeg", ".json", ".zip", ".log", ".html"],

    # --- Email and scheduled jobs -----------------------------------------------------
    # Who is told when a scheduled job fails (e.g. audit verification, backup).
    "QMS_ALERT_EMAILS": [],
    "QMS_BASE_URL": "http://127.0.0.1:8000",   # absolute links in emails
    "QMS_NOTIFICATIONS_ENABLED": True,
    "QMS_REMINDER_LOOKAHEAD_DAYS": 7,
    "QMS_REVIEW_REMINDER_DAYS": [60, 30, 7, 0],  # emails this many days before a review is due
    # Local clone of a git repository kept in step with the controlled documents. Empty: none.
    "QMS_DOCS_GIT_REPO": "",
    "QMS_DOCS_GIT_PUSH": False,
    # Daily jobs run by `manage.py run_scheduler`, as (HH:MM UTC, name, command). Projects add
    # their own (the standalone project adds the database backup).
    "QMS_SCHEDULED_JOBS": [
        ("03:00", "verify_audit", ["python", "manage.py", "verify_audit"]),
        ("05:30", "generate_pms_activities", ["python", "manage.py", "generate_pms_activities"]),
        ("05:45", "send_reminders", ["python", "manage.py", "send_reminders"]),
    ],

    # --- Documents, training, risk, suppliers -----------------------------------------
    "QMS_TRAINING_DUE_DAYS": 14,
    "QMS_INVITATION_DAYS": 14,       # invitation links expire after this many days by default
    "QMS_INVITATION_MAX_DAYS": 30,   # the longest expiry an inviter can choose
    "QMS_SOUP_REVIEW_DAYS": 35,      # SOUP anomaly lists reviewed at least monthly
    # Risk matrix: score = severity (1-5) x probability (1-5).
    "QMS_RISK_ACCEPTABLE_MAX": 4,    # score <= 4: acceptable
    "QMS_RISK_UNACCEPTABLE_MIN": 10,  # score >= 10: unacceptable; between: reduce as far as possible

    # --- Accounts, single sign-on and signatures --------------------------------------
    # New SSO accounts are created only for verified emails in these domains. Empty: SSO only
    # for accounts an administrator has already created.
    "QMS_SSO_ALLOWED_DOMAINS": [],
    # Account requests from the landing page: who may register, and the captcha that guards it.
    "QMS_ACCESS_REQUEST_PROVIDERS": ["google", "microsoft", "linkedin", "orcid"],
    "QMS_ACCESS_REQUEST_MINUTES": 15,   # after the captcha, time allowed to finish signing in
    "QMS_ACCESS_CONFIRM_DAYS": 2,       # validity of the email confirmation link
    "QMS_CAPTCHA": "pow",               # "pow" (self-hosted) or "turnstile"
    "QMS_CAPTCHA_DIFFICULTY": 100000,
    "QMS_CAPTCHA_TTL_SECONDS": 600,
    "QMS_TURNSTILE_SITE_KEY": "",
    "QMS_TURNSTILE_SECRET_KEY": "",
    # Minutes after login during which an SSO-only user may set their signing PIN.
    "QMS_PIN_REAUTH_MINUTES": 15,
    # Hosts on which Django admin answers (finding F7). Empty: every host (development).
    "QMS_ADMIN_HOSTS": [],
    # Who may sign (finding F6): providers signers must be connected to, and email domains.
    # Empty: no restriction (development, staging).
    "QMS_SIGNER_SSO_PROVIDERS": [],
    "QMS_SIGNER_EMAIL_DOMAINS": [],
}


def apply_defaults(settings):
    """Set each QMS_* setting the project left undefined to its default."""
    for name, value in DEFAULTS.items():
        if not hasattr(settings, name):
            setattr(settings, name, copy.deepcopy(value))
