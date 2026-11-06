"""
User requirements for SAMD_QMS and their traceability to verification.

Each requirement has an ID, a risk (H/M/L: impact on product safety, record integrity or
regulatory compliance if it failed), and either automated tests (run by ``manage.py run_oq``) or
a manual protocol from the validation plan (installation and performance qualification).

Keep this file in step with the validation plan: adding or changing a requirement is a change to
the validated state.
"""

REQUIREMENTS = [
    # id, area, requirement, risk, automated tests (module.Class.method), manual protocols
    ("URS-01", "Access", "Only signed-in users holding a QMS role can see QMS data.", "H",
     ["tests.ViewTests.test_login_required",
      "test_modules.SecurityTests.test_user_without_role_sees_pending_page"], []),
    ("URS-02", "Access", "People see and act only on devices whose team they belong to (they may "
     "be on several), unless they have All-device access. Enforced in pages, forms and business "
     "rules.", "H",
     ["test_teams.TeamTests.test_accessible_devices",
      "test_teams.TeamTests.test_other_teams_records_are_invisible",
      "test_teams.TeamTests.test_switcher_only_offers_own_devices",
      "test_teams.TeamTests.test_multi_team_member_and_head_see_both",
      "test_teams.TeamTests.test_documents",
      "test_teams.TeamTests.test_services_refuse_other_teams_even_when_called_directly",
      "test_teams.TeamTests.test_forms_refuse_other_teams_devices_hazards_and_links"],
     ["PQ-02"]),
    ("URS-03", "Access", "Device teams are managed by QA on the team or All-device users; changes "
     "are audited; a device always keeps a team member.", "M",
     ["test_teams.TeamTests.test_qa_on_team_manages_it_and_changes_are_audited",
      "test_teams.TeamTests.test_last_member_cannot_be_removed",
      "test_teams.TeamTests.test_device_creator_joins_team"], []),
    ("URS-04", "Access", "Single sign-on with Google, Microsoft, LinkedIn, ORCID and GitHub; no "
     "local self-sign-up; new SSO accounts only for verified emails in allowed domains; "
     "CSRF-safe start.", "H",
     ["test_modules.SSOTests.test_login_page_offers_all_five_providers",
      "test_modules.SSOTests.test_provider_redirects",
      "test_modules.SSOTests.test_get_does_not_start_login",
      "test_modules.SSOTests.test_signup_rules",
      "test_modules.SSOTests.test_provider_config_from_environment",
      "test_modules.ConnectedAccountsTests.test_page_offers_connect_buttons_for_configured_providers",
      "test_modules.ConnectedAccountsTests.test_page_explains_when_no_provider_is_switched_on",
      "test_modules.ConnectedAccountsTests.test_connected_account_is_listed_and_can_be_removed"],
     ["IQ-05", "PQ-01"]),
    ("URS-05", "Access", "Logins, failed logins and role changes are recorded.", "M",
     ["test_modules.SecurityTests.test_login_events_and_role_changes_are_audited"], []),

    ("URS-10", "Records", "Status changes only through defined workflow steps, each requiring "
     "its information before it is allowed.", "H",
     ["tests.ProblemReportWorkflowTests.test_full_lifecycle_with_traceability_and_signature",
      "tests.ProblemReportWorkflowTests.test_status_cannot_be_set_directly",
      "tests.ProblemReportWorkflowTests.test_reject_needs_comment",
      "tests.ViewTests.test_pages_render_and_transition_via_ui"], ["PQ-03"]),
    ("URS-11", "Records", "Workflow steps are restricted to the roles defined for them.", "H",
     ["tests.ProblemReportWorkflowTests.test_full_lifecycle_with_traceability_and_signature",
      "test_modules.SupplierTests.test_evaluation_requires_signature_and_qa"], []),
    ("URS-12", "Records", "Required traceability is enforced: a Problem Report needs its fixing "
     "Change Request; a reportable complaint needs its Incident.", "H",
     ["tests.ProblemReportWorkflowTests.test_full_lifecycle_with_traceability_and_signature",
      "tests.ComplaintTests.test_reportable_complaint_needs_incident_link"], []),
    ("URS-13", "Records", "Quality records cannot be deleted; closed records cannot be edited; "
     "every record belongs to a device.", "H",
     ["tests.ProblemReportWorkflowTests.test_records_cannot_be_deleted",
      "tests.ProblemReportWorkflowTests.test_closed_records_are_locked",
      "test_devices.DeviceScopingTests.test_records_must_have_a_device"], []),
    ("URS-14", "Records", "Incident reporting deadlines are calculated from the date aware and "
     "flagged when overdue.", "H",
     ["tests.IncidentTests.test_report_due_and_overdue"], ["PQ-04"]),
    ("URS-15", "Records", "Dates are validated (date aware cannot be in the future).", "L",
     ["tests.ComplaintTests.test_date_aware_cannot_be_future"], []),

    ("URS-20", "Signatures", "Approvals require re-entering a password or signing PIN; each "
     "signature records signer, meaning, time and a hash of the state signed.", "H",
     ["tests.ProblemReportWorkflowTests.test_full_lifecycle_with_traceability_and_signature",
      "test_modules.PageTests.test_signature_by_ui",
      "test_modules.SecurityTests.test_signing_pin_replaces_password"], []),
    ("URS-21", "Signatures", "Independent approval: authors cannot approve their own work.", "H",
     ["tests.IndependenceTests.test_author_cannot_approve_own_change",
      "test_modules.DocumentControlTests.test_full_lifecycle_supersedes_and_assigns_training",
      "test_devices.TechnicalFileBuildTests.test_approval_rules"], []),
    ("URS-22", "Signatures", "Signatures cannot be changed or deleted.", "H",
     ["tests.AuditTests.test_signatures_are_immutable"], []),
    ("URS-23", "Signatures", "Users without a local password (SSO) can only sign with a "
     "signing PIN.", "M",
     ["test_modules.SecurityTests.test_sso_user_without_password_cannot_sign_without_pin"],
     ["PQ-01"]),

    ("URS-30", "Audit trail", "Every create and change is recorded with who, when, and old and "
     "new values.", "H",
     ["tests.AuditTests.test_changes_are_logged_with_actor",
      "test_devices.DeviceScopingTests.test_device_changes_and_soup_links_are_audited",
      "test_modules.RiskTests.test_record_hazard_links_are_audited"], []),
    ("URS-31", "Audit trail", "The audit trail is append-only and any tampering is detected.", "H",
     ["tests.AuditTests.test_audit_events_are_immutable",
      "tests.AuditTests.test_tampering_is_detected"], ["IQ-06"]),
    ("URS-32", "Audit trail", "The full audit trail is limited to people with All-device "
     "access; per-object trails follow team access.", "M",
     ["test_teams.TeamTests.test_full_audit_trail_needs_all_device_access"], []),

    ("URS-40", "Documents", "Controlled documents follow draft, review, signed approval and "
     "effective; a new effective version supersedes the old; withdrawal is signed.", "H",
     ["test_modules.DocumentControlTests.test_full_lifecycle_supersedes_and_assigns_training",
      "test_modules.DocumentControlTests.test_return_needs_comment_and_obsolete_locks"],
     ["PQ-05"]),
    ("URS-41", "Documents", "Document files are frozen after submission and verified by "
     "checksum before approval and download.", "H",
     ["test_modules.DocumentControlTests.test_submit_requires_file_and_approval_detects_tampering"],
     []),
    ("URS-42", "Training", "Training is assigned to the required roles (and device team) when a "
     "version becomes effective, including new joiners, and completed with a signature.", "M",
     ["test_modules.TrainingTests.test_complete_own_training_with_signature",
      "test_modules.TrainingTests.test_new_joiner_gets_training_via_sync",
      "test_modules.TrainingTests.test_matrix",
      "test_teams.TeamTests.test_training_for_device_documents_goes_to_the_team"], []),

    ("URS-50", "Risk", "Residual risk can only be accepted when scored, controlled, verified "
     "and, if above acceptable, justified; acceptance is signed and locks the hazard.", "H",
     ["test_modules.RiskTests.test_acceptance_rules",
      "test_modules.RiskTests.test_alarp_residual_needs_benefit_risk",
      "test_modules.RiskTests.test_matrix"], ["PQ-06"]),

    ("URS-55", "Suppliers", "Supplier approval needs a signed QA evaluation; SOUP anomaly "
     "reviews are tracked.", "M",
     ["test_modules.SupplierTests.test_evaluation_requires_signature_and_qa",
      "test_modules.SupplierTests.test_soup_review_overdue"], []),
    ("URS-60", "Attachments", "Uploads are type- and size-checked, need a no-participant-data "
     "confirmation, are checksummed and cannot be changed.", "M",
     ["test_modules.AttachmentTests.test_upload_checksum_and_immutability"], []),
    ("URS-65", "PMS", "Each device gets a PMS schedule; activities are created ahead of their due "
     "date without duplicates.", "M",
     ["tests.PMSTests.test_generation_is_idempotent_and_advances",
      "tests.PMSTests.test_add_months_month_end",
      "tests.PMSTests.test_seed_command",
      "test_devices.DeviceScopingTests.test_pms_setup_per_device_and_activities_carry_device",
      "test_devices.DeviceScopingTests.test_only_qa_creates_devices_and_pms_is_scheduled"],
     ["IQ-07"]),
    ("URS-66", "Notifications", "Emails reach the right people, only on the device's team, "
     "including urgent incident alerts and daily reminders.", "M",
     ["test_modules.NotificationTests.test_incident_and_assignment_emails",
      "test_modules.NotificationTests.test_daily_reminders",
      "test_teams.TeamTests.test_notifications_go_only_to_the_team"], ["IQ-04"]),

    ("URS-70", "Devices", "Data is kept per device; the device switcher filters every list "
     "safely.", "M",
     ["test_devices.DeviceScopingTests.test_switcher_filters_lists",
      "test_devices.DeviceScopingTests.test_switcher_rejects_external_redirect",
      "test_devices.CompletenessTests.test_other_devices_data_is_excluded"], []),
    ("URS-71", "Technical file", "The technical file contains the device's data and effective "
     "documents in MDR Annex II/III order, and the completeness check reports gaps correctly.",
     "H",
     ["test_devices.CompletenessTests.test_empty_device_has_errors",
      "test_devices.CompletenessTests.test_complete_device_has_no_gaps",
      "test_devices.CompletenessTests.test_on_market_requires_declaration_and_unaccepted_unacceptable_risk_is_error",
      "test_devices.CompletenessTests.test_qms_wide_documents_count_for_every_device",
      "test_devices.TechnicalFileBuildTests.test_package_contents_manifest_and_formats"],
     ["PQ-07"]),
    ("URS-72", "Technical file", "Builds are frozen and checksummed; approval needs QA, no "
     "errors, justified warnings and an independent signature.", "H",
     ["test_devices.TechnicalFileBuildTests.test_builds_are_frozen",
      "test_devices.TechnicalFileBuildTests.test_approval_rules",
      "test_devices.TechnicalFileBuildTests.test_download_detects_tampering"], []),
    ("URS-73", "Devices", "Each device defines its own software items; records, hazards and SOUP "
     "items accept only their device's items; data from earlier releases is migrated without "
     "changing its meaning.", "M",
     ["test_devices.SoftwareItemTests.test_list_ignores_blanks_and_duplicates",
      "test_devices.SoftwareItemTests.test_record_must_use_its_devices_items_and_spelling_is_normalised",
      "test_devices.SoftwareItemTests.test_device_without_a_list_accepts_any_item",
      "test_devices.SoftwareItemTests.test_suggestions_come_only_from_the_users_devices",
      "test_devices.SoftwareItemTests.test_hazard_and_soup_forms_check_items",
      "test_devices.SoftwareItemTests.test_device_page_lists_items",
      "test_devices.SoftwareItemMigrationTests.test_codes_become_labels_and_device_lists_are_filled"],
     []),
    ("URS-80", "Usability", "Every page renders for authorised users.", "L",
     ["test_modules.PageTests.test_all_pages_render",
      "test_devices.TechnicalFileBuildTests.test_pages"], ["PQ-08"]),
    ("URS-81", "Usability", "Every page links to the help for that page, every form field has a "
     "help icon, and the help ships with the release so it matches the version in use.", "L",
     ["test_help.HelpContentTests.test_every_page_has_a_help_section_that_exists",
      "test_help.HelpContentTests.test_every_form_field_has_help_and_a_reference_entry",
      "test_help.HelpContentTests.test_plain_html_fields_use_registered_help",
      "test_help.HelpContentTests.test_every_plain_input_in_templates_has_a_help_icon",
      "test_help.HelpContentTests.test_topics_render_with_their_field_reference",
      "test_help.HelpContentTests.test_help_has_no_device_specific_names",
      "test_help.HelpPageTests.test_help_is_open_without_signing_in",
      "test_help.HelpPageTests.test_header_links_to_the_help_for_the_current_page",
      "test_help.HelpPageTests.test_each_visible_form_field_gets_an_icon",
      "test_help.HelpPageTests.test_icon_markup_is_accessible_and_escaped",
      "test_help.HelpPageTests.test_pages_render_for_qa_with_help_link"], ["PQ-08"]),

    # Verified only manually, in the target environment
    ("URS-90", "Operation", "Data and files can be backed up and restored without loss, and the "
     "audit chain verifies after restore.", "H", [], ["IQ-08"]),
    ("URS-91", "Operation", "The service is reachable only over HTTPS, with secure cookies and "
     "session time-out.", "H", [], ["IQ-03"]),
    ("URS-92", "Operation", "Scheduled jobs (backup, PMS generation, reminders, audit "
     "verification) run daily and alert on failure.", "M",
     ["test_ops.SchedulerTests.test_next_run",
      "test_ops.SchedulerTests.test_failed_job_sends_alert_and_successful_job_does_not",
      "test_ops.SchedulerTests.test_missing_command_is_a_failure",
      "test_ops.SchedulerTests.test_alert_needs_recipients",
      "test_ops.SchedulerTests.test_unknown_job_is_refused"], ["IQ-07"]),
    ("URS-94", "Operation", "A health endpoint reports whether the database and file storage "
     "work, without login and without revealing data, for the proxy and monitoring.", "M",
     ["test_ops.HealthTests.test_healthz_ok_without_login_and_reveals_only_status",
      "test_ops.HealthTests.test_healthz_fails_when_storage_is_unavailable",
      "test_ops.HealthTests.test_healthz_is_get_only"], ["IQ-03"]),
    ("URS-93", "Operation", "Response times are acceptable with the expected data volume.", "L",
     [], ["PQ-08"]),
]


def automated_test_ids():
    return {t for r in REQUIREMENTS for t in r[4]}
