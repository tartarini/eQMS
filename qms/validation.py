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
    ("URS-03", "Access", "Device teams and the roles on them are managed by Device admins and QA "
     "on the device; nobody changes their own roles; changes are audited; a device always keeps "
     "a member, and one who can manage its team.", "H",
     ["test_teams.TeamTests.test_qa_on_team_manages_it_and_changes_are_audited",
      "test_teams.TeamTests.test_last_member_cannot_be_removed",
      "test_teams.TeamTests.test_device_creator_joins_team",
      "test_roles.TeamPageTests.test_device_admin_changes_roles_and_it_is_audited",
      "test_roles.TeamPageTests.test_nobody_changes_their_own_roles",
      "test_roles.TeamPageTests.test_engineer_cannot_change_roles",
      "test_roles.TeamPageTests.test_a_team_keeps_someone_who_can_manage_it",
      "test_roles.TeamPageTests.test_adding_an_existing_user_needs_roles",
      "test_roles.TeamPageTests.test_team_panel_shows_roles_per_device",
      "test_roles.TeamPageTests.test_device_creator_is_qa_and_device_admin"], []),
    ("URS-06", "Access", "Roles are held per device: a person can hold different roles on "
     "different devices, and every role check (workflow steps, approvals, emails, training) uses "
     "the role on the item's device. Roles from earlier releases are moved onto teams without "
     "anyone gaining or losing a permission.", "H",
     ["test_roles.PerDeviceRoleTests.test_roles_apply_only_on_their_device",
      "test_roles.PerDeviceRoleTests.test_workflow_approval_checks_the_records_device",
      "test_roles.PerDeviceRoleTests.test_organisation_wide_role_applies_only_where_the_person_can_see",
      "test_roles.PerDeviceRoleTests.test_inactive_membership_or_retired_device_gives_no_role",
      "test_roles.PerDeviceRoleTests.test_device_admin_manages_team_but_cannot_approve_or_open_records",
      "test_roles.PerDeviceRoleTests.test_set_roles_validates_and_orders",
      "test_roles.PerDeviceRoleTests.test_emails_go_to_the_role_on_that_device",
      "test_roles.PerDeviceRoleTests.test_training_follows_the_role_on_the_documents_device",
      "test_roles.RoleMigrationTests.test_roles_move_to_teams"], ["PQ-02"]),
    ("URS-07", "Access", "Device admins and QA invite people by email to the devices whose team "
     "they manage, with roles on each. A new person registers from the link only with single "
     "sign-on that verifies the invited address; no local username and password. The link is "
     "single use, expires, can only be accepted by an account with the invited address, can be "
     "resent or revoked, and is stored only as a hash; invitations and acceptances are "
     "audited.", "H",
     ["test_invitations.InvitationTests.test_invitation_email_lists_devices_roles_and_expiry",
      "test_invitations.InvitationTests.test_only_the_token_hash_is_stored",
      "test_invitations.InvitationTests.test_you_can_only_grant_roles_on_teams_you_manage",
      "test_invitations.InvitationTests.test_input_is_checked",
      "test_invitations.InvitationTests.test_one_pending_invitation_per_person_and_device",
      "test_invitations.InvitationTests.test_new_person_registers_only_with_single_sign_on",
      "test_invitations.InvitationTests.test_without_single_sign_on_nobody_can_register_from_an_invitation",
      "test_invitations.InvitationTests.test_new_person_registers_with_single_sign_on_and_joins_each_team",
      "test_invitations.InvitationTests.test_existing_account_signs_in_and_roles_are_added_not_replaced",
      "test_invitations.InvitationTests.test_another_account_cannot_accept",
      "test_invitations.InvitationTests.test_expired_invitation_is_refused_until_resent",
      "test_invitations.InvitationTests.test_revoked_invitation_cannot_be_used",
      "test_invitations.InvitationTests.test_grants_are_rechecked_when_accepted",
      "test_invitations.InvitationTests.test_unknown_link_is_not_found",
      "test_invitations.InvitationTests.test_invite_page_lists_only_managed_devices",
      "test_invitations.InvitationTests.test_invitations_page_and_device_panel",
      "test_invitations.InvitationTests.test_single_sign_on_signup_allowed_only_for_the_invited_address"], ["PQ-09"]),
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

    ("URS-08", "Access", "Visitors see a public landing page describing SAMD_QMS (at most 300 "
     "words) with no QMS data. They can request an account only after passing a captcha and "
     "then registering with single sign-on (Google, Microsoft, LinkedIn or ORCID); no local "
     "self-sign-up. A captcha solution is signed, expires and works once for the browser it "
     "was issued to. An email address not verified by the provider is confirmed by link "
     "before the request is reviewed.", "H",
     ["test_access_requests.LandingTests.test_visitors_get_the_landing_page_in_under_300_words",
      "test_access_requests.LandingTests.test_signed_in_members_get_the_dashboard",
      "test_access_requests.LandingTests.test_sign_in_page_links_to_the_request",
      "test_access_requests.CaptchaTests.test_solution_is_accepted_once",
      "test_access_requests.CaptchaTests.test_wrong_tampered_expired_or_foreign_solutions_fail",
      "test_access_requests.CaptchaTests.test_turnstile_backend_checks_the_token_with_cloudflare",
      "test_access_requests.RegistrationTests.test_captcha_then_only_the_four_providers",
      "test_access_requests.RegistrationTests.test_sso_may_create_an_account_only_after_the_captcha_and_with_allowed_providers",
      "test_access_requests.RegistrationTests.test_orcid_registration_end_to_end_creates_a_roleless_account",
      "test_access_requests.RegistrationTests.test_signed_in_people_skip_the_captcha",
      "test_access_requests.RequestAndReviewTests.test_verified_email_goes_straight_to_review",
      "test_access_requests.RequestAndReviewTests.test_orcid_email_is_confirmed_by_link_first",
      "test_access_requests.RequestAndReviewTests.test_one_open_request_and_none_for_people_with_access"],
     ["PQ-10"]),
    ("URS-09", "Access", "An account request gives no access. Device admins and QA see requests "
     "and approve one by adding the person to a device team they manage, with roles; only QA "
     "declines, with a reason emailed to the person. Decisions are final and audited.", "H",
     ["test_access_requests.RequestAndReviewTests.test_request_gives_no_access_until_approved",
      "test_access_requests.RequestAndReviewTests.test_device_admin_or_qa_approves_onto_a_team_they_manage",
      "test_access_requests.RequestAndReviewTests.test_qa_declines_with_a_reason",
      "test_access_requests.RequestAndReviewTests.test_list_is_for_team_managers_only"],
     ["PQ-10"]),
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
    ("URS-24", "Signatures", "On production, only people whose identity is confirmed by an "
     "approved institutional single sign-on provider (connected account, and a verified email "
     "address at an approved domain when domains are set) can sign; this applies to "
     "superusers too. Other environments are not restricted.", "H",
     ["test_signer_identity.SignerIdentityTests.test_without_the_setting_anyone_with_the_role_signs",
      "test_signer_identity.SignerIdentityTests.test_password_only_account_cannot_sign_even_as_superuser",
      "test_signer_identity.SignerIdentityTests.test_other_providers_do_not_count",
      "test_signer_identity.SignerIdentityTests.test_allowed_provider_needs_a_verified_address_at_the_domain",
      "test_signer_identity.SignerIdentityTests.test_institutional_account_signs_and_wrong_secret_still_fails",
      "test_signer_identity.SignerIdentityTests.test_domains_are_optional"],
     ["IQ-05", "PQ-01"]),

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
     "safely. After sign-in people see the devices whose team they are on, with their roles on "
     "each, and open one device's QMS; Devices in the top bar switches to another.", "M",
     ["test_devices.DeviceScopingTests.test_switcher_filters_lists",
      "test_devices.DeviceScopingTests.test_switcher_rejects_external_redirect",
      "test_devices.DeviceChoiceTests.test_sign_in_lands_on_the_list_of_your_devices_and_roles",
      "test_devices.DeviceChoiceTests.test_a_link_followed_before_signing_in_still_wins",
      "test_devices.DeviceChoiceTests."
      "test_opening_a_device_loads_its_qms_and_devices_switches_to_another",
      "test_devices.DeviceChoiceTests.test_cannot_open_a_device_whose_team_you_are_not_on",
      "test_devices.DeviceChoiceTests.test_device_admin_alone_sees_the_role_but_no_open_button",
      "test_devices.DeviceChoiceTests.test_organisation_wide_roles_are_marked",
      "test_ui.DeviceSwitcherTests.test_sign_in_shows_your_devices_and_opens_one",
      "test_devices.CompletenessTests.test_other_devices_data_is_excluded"], []),
    ("URS-74", "Devices", "The organisation profile records the organisation's EU MDR economic "
     "operator roles (manufacturer, authorised representative, importer, distributor); each "
     "device records which of them apply, shown on the device page and in technical file "
     "section 1. Only QA held organisation-wide changes the profile, and changes are audited.",
     "M",
     ["test_organisation.OrganisationProfileTests."
      "test_organisation_wide_qa_sets_up_the_profile_and_it_is_audited",
      "test_organisation.OrganisationProfileTests.test_device_level_qa_cannot_change_the_profile",
      "test_organisation.OrganisationProfileTests."
      "test_a_role_still_set_on_a_device_cannot_be_removed",
      "test_organisation.DeviceOperatorRoleTests.test_device_offers_only_the_organisations_roles",
      "test_organisation.DeviceOperatorRoleTests.test_a_profile_without_roles_offers_all_four",
      "test_organisation.DeviceOperatorRoleTests."
      "test_manufacturer_role_fills_in_the_manufacturer_from_the_profile",
      "test_organisation.DeviceOperatorRoleTests.test_an_entered_manufacturer_is_kept",
      "test_organisation.DeviceOperatorRoleTests."
      "test_role_shows_on_the_device_page_and_in_the_technical_file",
      "test_organisation.DeviceOperatorRoleTests."
      "test_completeness_check_warns_until_the_role_is_set"], []),
    ("URS-71", "Technical file", "The technical file contains the device's data and effective "
     "documents in MDR Annex II/III order, and the completeness check reports gaps correctly.",
     "H",
     ["test_devices.CompletenessTests.test_empty_device_has_errors",
      "test_devices.CompletenessTests.test_each_framework_offers_its_own_classes",
      "test_devices.CompletenessTests."
      "test_a_market_with_its_class_not_determined_blocks_approval",
      "test_devices.CompletenessTests.test_technical_file_lists_the_class_for_each_market",
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
    ("URS-82", "Usability", "Every page, including sign-in, help and administration, shows the "
     "release version and source commit at the top and the copyright notice at the foot; the "
     "health endpoint and OQ evidence report the same commit.", "M",
     ["test_release.ReleaseBannerTests.test_signed_out_pages",
      "test_release.ReleaseBannerTests.test_signed_in_pages",
      "test_release.ReleaseBannerTests.test_admin_pages",
      "test_release.ReleaseBannerTests.test_unknown_commit_is_shown_as_unknown",
      "test_release.ReleaseBannerTests.test_oq_report_carries_the_notice_and_commit",
      "test_ops.HealthTests.test_healthz_ok_without_login_and_reveals_only_status"],
     ["IQ-01"]),
    ("URS-83", "Usability", "The main user journeys work in a real web browser (Chromium) with "
     "no script errors: signing in from the landing page, every main page, help links and "
     "field help, the device switcher, raising and signing a record, the account-request "
     "captcha, and the invitation page.", "M",
     ["test_ui.SignInAndNavigationTests.test_visitor_sees_the_landing_page_and_signs_in",
      "test_ui.SignInAndNavigationTests.test_every_main_page_opens_without_browser_errors",
      "test_ui.SignInAndNavigationTests.test_help_link_and_field_help_popover",
      "test_ui.DeviceSwitcherTests.test_switcher_limits_the_record_list_to_one_device",
      "test_ui.RecordWorkflowTests.test_problem_report_from_creation_to_a_signed_rejection",
      "test_ui.RegistrationTests.test_captcha_is_solved_in_the_browser_then_providers_are_offered",
      "test_ui.RegistrationTests.test_invitation_link_offers_only_single_sign_on"],
     ["PQ-08"]),
    ("URS-90", "Operation", "Data and files can be backed up and restored without loss, and the "
     "audit chain verifies after restore.", "H", [], ["IQ-08"]),
    ("URS-91", "Operation", "The service is reachable only over HTTPS, with secure cookies and "
     "session time-out. On production, Django admin answers only through the SSH tunnel, not "
     "on the public site.", "H",
     ["test_admin_access.AdminAccessTests.test_admin_answers_everywhere_when_no_hosts_are_set",
      "test_admin_access.AdminAccessTests.test_admin_only_through_the_tunnel_host"], ["IQ-03"]),
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
    ("URS-95", "Records", "Management reviews are recorded with their attendees, the inputs "
     "considered, the decisions and the resource needs, and closed only with a QA signature.", "H",
     ["test_compliance_records.ManagementReviewTests.test_held_review_needs_inputs_and_closes_with_outputs"], []),
    ("URS-96", "Records", "Internal audits cannot be led by the auditee of the area audited, and "
     "are closed by someone other than their author (ISO 13485 8.2.4).", "H",
     ["test_compliance_records.InternalAuditTests.test_lead_auditor_cannot_audit_their_own_area",
      "test_compliance_records.InternalAuditTests.test_independent_auditor_runs_and_qa_closes",
      "test_compliance_records.InternalAuditTests.test_closer_may_not_be_the_record_author"], []),
    ("URS-97", "Records", "Nonconforming product is dispositioned by QA, a concession needs its "
     "justification and the risk file checked, and the disposition is verified before closure "
     "(ISO 13485 8.3).", "H",
     ["test_compliance_records.NonconformanceTests.test_disposition_needs_a_choice_and_qa_signature",
      "test_compliance_records.NonconformanceTests.test_concession_needs_justification_and_risk_file_checked",
      "test_compliance_records.NonconformanceTests.test_disposition_is_verified_then_closed"], []),
    ("URS-98", "Records", "Design inputs, outputs and reviews need acceptance criteria, and design "
     "reviews need participants and a date; approval is independent and locks the record "
     "(ISO 13485 7.3.3 to 7.3.5).", "H",
     ["test_compliance_records.DesignControlTests.test_output_needs_acceptance_criteria",
      "test_compliance_records.DesignControlTests.test_review_needs_participants_and_date",
      "test_compliance_records.DesignControlTests.test_approval_is_independent"], []),
    ("URS-99", "Records", "Closed records and withdrawn documents are kept for the device's "
     "expected lifetime and at least two years, and the retention end date is reported; "
     "nothing is deleted (ISO 13485 4.2.4, 4.2.5).", "M",
     ["test_compliance_records.RetentionTests.test_add_years_handles_leap_day",
      "test_compliance_records.RetentionTests.test_minimum_is_two_years_without_lifetime",
      "test_compliance_records.RetentionTests.test_expected_lifetime_extends_retention",
      "test_compliance_records.RetentionTests.test_closed_record_and_withdrawn_document_are_listed",
      "test_compliance_records.RetentionTests.test_report_command_prints_items_and_flags_missing_lifetime",
      "test_compliance_records.RecordPrefixTests.test_new_types_have_prefixes_and_fields"], []),
    ("URS-100", "Records", "Nonconforming product and design control records can be rejected only "
     "with a stated reason, and a rejected record is locked.", "H",
     ["test_compliance_records.RejectionTests.test_nonconformance_can_be_rejected_with_a_reason",
      "test_compliance_records.RejectionTests.test_design_review_can_be_rejected_with_a_reason"],
     []),
    ("URS-101", "Records", "The management review, internal audit, nonconforming product and "
     "design control records can be created and moved on in the browser, and a step is refused "
     "in the browser when its required fields are missing.", "H",
     ["test_compliance_records.WebUITests.test_each_new_type_is_created_and_detail_renders",
      "test_compliance_records.WebUITests.test_transition_is_refused_in_the_browser_without_required_fields"],
     []),
    ("URS-102", "Records", "Withdrawn QMS-wide documents are kept for the longest expected lifetime "
     "of the active devices, and each device's expected lifetime can be set on its record.", "M",
     ["test_compliance_records.RetentionOfQmsWideDocumentTests.test_qms_wide_document_uses_the_longest_device_lifetime",
      "test_compliance_records.WebUITests.test_device_form_offers_expected_lifetime"],
     []),
    ("URS-103", "Devices", "Each device's page shows its documentation route: six stages from "
     "set-up to release and post-market, each with checks worked out from the QMS's own data, "
     "the gate checks marked, and a link to where each open check is fixed.", "L",
     ["test_doc_route.DocumentationRouteTests.test_new_device_starts_at_stage_one_with_nothing_done_beyond_its_record",
      "test_doc_route.DocumentationRouteTests.test_checks_follow_the_device_record",
      "test_doc_route.DocumentationRouteTests.test_risk_gate_needs_a_control_on_every_hazard",
      "test_doc_route.DocumentationRouteTests.test_evidence_documents_complete_stage_five",
      "test_doc_route.DocumentationRouteTests.test_overall_is_the_share_of_checks_that_pass",
      "test_doc_route.DocumentationRouteTests.test_device_page_shows_the_route_with_links_to_fix_open_checks"],
     []),
    ("URS-104", "Access", "The People page lists the people on the devices you can see, with their "
     "roles on each, and organisation-wide role holders read-only. Edit controls appear only to "
     "people who can manage that device's team, and never on their own row.", "H",
     ["test_people.PeopleTests.test_lists_only_people_on_visible_devices",
      "test_people.PeopleTests.test_people_without_manage_rights_see_no_edit_controls",
      "test_people.PeopleTests.test_manager_sees_controls_but_not_for_own_row",
      "test_people.PeopleTests.test_organisation_wide_roles_are_listed_read_only"],
     []),
    ("URS-105", "Access", "A team manager can add an existing account to a device team, change a "
     "member's roles and responsibility, and remove a member (deactivated, not deleted), only on "
     "devices whose team they manage. Each change is audited, and the page returns only to an "
     "address on this site.", "H",
     ["test_people.PeopleTests.test_manager_adds_existing_account_and_it_is_audited",
      "test_people.PeopleTests.test_manager_changes_roles_and_it_is_audited",
      "test_people.PeopleTests.test_manager_removes_person_and_it_is_audited",
      "test_people.PeopleTests.test_manager_cannot_change_roles_on_another_device",
      "test_people.PeopleTests.test_return_address_must_be_on_this_site"],
     []),
    ("URS-106", "Access", "Someone holding several roles can choose one to act as for their "
     "session (all roles by default). The choice only narrows: it limits their permissions on "
     "the device and the functions shown, a role they don't hold can't be chosen, and one they no "
     "longer hold is dropped. The switcher appears only to people with several roles, and "
     "returns only to an address on this site.", "H",
     ["test_role_lens.ActingAsTests.test_all_roles_by_default",
      "test_role_lens.ActingAsTests.test_choosing_a_role_limits_the_functions_shown",
      "test_role_lens.ActingAsTests.test_choice_limits_permissions_on_the_device",
      "test_role_lens.ActingAsTests.test_cannot_choose_a_role_not_held",
      "test_role_lens.ActingAsTests.test_a_held_role_no_longer_held_is_dropped",
      "test_role_lens.ActingAsTests.test_switcher_only_shown_to_people_with_several_roles",
      "test_role_lens.ActingAsTests.test_return_address_must_be_on_this_site",
      "test_role_lens.ActingAsTests.test_functions_follow_the_workflow"],
     []),
    ("URS-107", "Usability", "Each device has a task board for each person with a role on it: "
     "workflow steps they can take now (to do), steps of theirs waiting on another role, and "
     "done. Closed records drop off. People with no role on the device get no board and can't "
     "open its page.", "M",
     ["test_tasks.TaskBoardTests.test_qa_sees_the_closing_step_to_do",
      "test_tasks.TaskBoardTests.test_engineer_owner_sees_it_waiting_on_qa",
      "test_tasks.TaskBoardTests.test_closed_records_drop_off_the_board",
      "test_tasks.TaskBoardTests.test_nobody_without_a_role_on_the_device_gets_a_board",
      "test_tasks.TaskBoardTests.test_page_shows_the_board_to_a_member",
      "test_tasks.TaskBoardTests.test_page_refuses_someone_with_no_role_on_the_device"],
     []),
    ("URS-108", "Devices", "Each device has an approval gate for stages 2, 4, 5 and 6 of its "
     "documentation route, created once. Only the gate's approver role can approve it, and the "
     "approver is recorded. An open gate is a to-do only for people who can approve it, and the "
     "gate list says whether the viewer can approve each one now.", "H",
     ["test_tasks.StageGateTests.test_gates_are_created_for_the_device_route",
      "test_tasks.StageGateTests.test_only_the_approver_role_can_approve_a_gate",
      "test_tasks.StageGateTests.test_open_gate_is_to_do_for_its_approver_only",
      "test_tasks.StageGateTests.test_gate_lanes_say_who_can_approve_now"],
     []),
    ("URS-109", "Devices", "A device team's roles are visible to its members. Device admins and QA can change a person's roles, remove them from the team and add an existing account, each change is audited, and organisation-wide roles are shown read-only. A person cannot change their own roles, and a return address must be on this site.", "H",
     [
      "test_people.PeopleTests.test_lists_only_people_on_visible_devices",
      "test_people.PeopleTests.test_people_without_manage_rights_see_no_edit_controls",
      "test_people.PeopleTests.test_manager_sees_controls_but_not_for_own_row",
      "test_people.PeopleTests.test_manager_changes_roles_and_it_is_audited",
      "test_people.PeopleTests.test_manager_removes_person_and_it_is_audited",
      "test_people.PeopleTests.test_manager_adds_existing_account_and_it_is_audited",
      "test_people.PeopleTests.test_manager_cannot_change_roles_on_another_device",
      "test_people.PeopleTests.test_return_address_must_be_on_this_site",
      "test_people.PeopleTests.test_organisation_wide_roles_are_listed_read_only"],
     []),
    ("URS-110", "Devices", "A person who holds several roles can work as one of them. The choice only narrows what they can do, a role they do not hold cannot be chosen, and a stale choice is dropped.", "H",
     [
      "test_role_lens.ActingAsTests.test_all_roles_by_default",
      "test_role_lens.ActingAsTests.test_choosing_a_role_limits_the_functions_shown",
      "test_role_lens.ActingAsTests.test_choice_limits_permissions_on_the_device",
      "test_role_lens.ActingAsTests.test_cannot_choose_a_role_not_held",
      "test_role_lens.ActingAsTests.test_a_held_role_no_longer_held_is_dropped",
      "test_role_lens.ActingAsTests.test_switcher_only_shown_to_people_with_several_roles",
      "test_role_lens.ActingAsTests.test_return_address_must_be_on_this_site",
      "test_role_lens.ActingAsTests.test_functions_follow_the_workflow"],
     []),
    ("URS-111", "Tasks", "Each person's task board for a device shows only the work their roles there can take now, the work they are waiting on, and what they signed recently. A person with no role on the device gets no board.", "M",
     [
      "test_tasks.TaskBoardTests.test_nobody_without_a_role_on_the_device_gets_a_board",
      "test_tasks.TaskBoardTests.test_page_refuses_someone_with_no_role_on_the_device",
      "test_tasks.TaskBoardTests.test_page_shows_the_board_to_a_member",
      "test_tasks.TaskBoardTests.test_qa_sees_the_closing_step_to_do",
      "test_tasks.TaskBoardTests.test_engineer_owner_sees_it_waiting_on_qa",
      "test_tasks.TaskBoardTests.test_closed_records_drop_off_the_board"],
     []),
    ("URS-112", "Approvals", "Approver gates for a device's route open in stage order. Only the holder of the gate's approver role can approve it, approval is an electronic signature, and the next approver is notified when a gate opens.", "H",
     [
      "test_tasks.StageGateTests.test_gates_are_created_for_the_device_route",
      "test_tasks.StageGateTests.test_only_the_approver_role_can_approve_a_gate",
      "test_tasks.StageGateTests.test_gates_open_in_stage_order",
      "test_tasks.StageGateTests.test_approval_is_signed",
      "test_tasks.StageGateTests.test_approval_tells_the_next_approver",
      "test_tasks.StageGateTests.test_open_gate_is_to_do_for_its_approver_only",
      "test_tasks.StageGateTests.test_gate_lanes_say_who_can_approve_now"],
     []),
    ("URS-113", "Documents", "Each document's review is reminded to its owner and device QA once at each stage before the review date and once when overdue.", "M",
     [
      "test_doc_exchange.ReviewReminderTests.test_one_email_per_stage_and_again_when_the_date_changes",
      "test_doc_exchange.ReviewReminderTests.test_no_email_far_from_the_review_date",
      "test_doc_exchange.ReviewReminderTests.test_overdue_document_is_reported_once"],
     []),
    ("URS-114", "Documents", "Effective documents can be exported as folders and zip archives, and markdown files can be imported as draft documents or revisions. Only documents the person can see are exported, and an import needs team membership on the device.", "H",
     [
      "test_doc_exchange.ExportTests.test_export_has_folder_per_document_with_file_and_markdown",
      "test_doc_exchange.ExportTests.test_draft_documents_are_not_exported",
      "test_doc_exchange.ExportTests.test_export_only_shows_documents_the_user_can_see",
      "test_doc_exchange.ExportTests.test_zip_download_for_a_signed_in_user",
      "test_doc_exchange.ImportTests.test_new_markdown_becomes_a_draft_document",
      "test_doc_exchange.ImportTests.test_cannot_import_onto_a_device_you_are_not_on",
      "test_doc_exchange.ImportTests.test_bad_front_matter_is_reported_and_skipped",
      "test_doc_exchange.ImportTests.test_only_markdown_or_zip_is_accepted",
      "test_doc_exchange.ImportTests.test_exported_document_comes_back_as_a_revision",
      "test_doc_exchange.ImportTests.test_zip_of_markdown_imports_each_file",
      "test_doc_exchange.ImportTests.test_import_page_creates_documents"],
     []),
    ("URS-115", "Documents", "A documents git clone is kept in step with the QMS: it commits only when something changed, removes effective documents that are withdrawn, and refuses a folder that is not a git clone.", "M",
     [
      "test_doc_exchange.GitSyncTests.test_commits_changes_and_stays_quiet_when_nothing_changed",
      "test_doc_exchange.GitSyncTests.test_new_effective_version_is_committed",
      "test_doc_exchange.GitSyncTests.test_withdrawn_document_is_removed_from_the_repository",
      "test_doc_exchange.GitSyncTests.test_refuses_a_folder_that_is_not_a_clone"],
     []),
    ("URS-116", "Devices", "A QMS admin manages the application overall: they see every device and can manage every device team without being on it, and only they can appoint or remove a Device admin. A QMS admin holds no working role and signs nothing. Device admins keep managing the other roles on their own teams.", "H",
     [
      "test_qms_admin.QmsAdminTests.test_qms_admin_sees_and_manages_every_device_without_a_membership",
      "test_qms_admin.QmsAdminTests.test_ordinary_user_is_not_a_qms_admin",
      "test_qms_admin.QmsAdminTests.test_device_admin_cannot_add_a_device_admin",
      "test_qms_admin.QmsAdminTests.test_device_admin_cannot_remove_device_admin_from_another_admin",
      "test_qms_admin.QmsAdminTests.test_device_admin_cannot_remove_a_device_admin_from_the_team",
      "test_qms_admin.QmsAdminTests.test_device_admin_can_still_change_ordinary_roles",
      "test_qms_admin.QmsAdminTests.test_qms_admin_appoints_a_device_admin_and_it_is_audited",
      "test_qms_admin.QmsAdminTests.test_qms_admin_removes_a_device_admin",
      "test_qms_admin.QmsAdminTests.test_device_admin_cannot_invite_as_device_admin",
      "test_qms_admin.QmsAdminTests.test_device_admin_can_still_invite_an_engineer",
      "test_qms_admin.QmsAdminTests.test_qms_admin_can_invite_as_device_admin"],
     []),
    ("URS-117", "Devices", "The documentation route panel follows the route set on the device "
     "record (Greenfield stages 1-6 or Retrofit steps A-G), draws it as a diagram, and shows each "
     "approver gate's sign-off beside its checks: approved, awaiting sign-off, checks not passing, "
     "or approved but checks no longer passing. A gate can't be signed while its gate checks fail: "
     "the approver's card and the gate-open email list the failing checks, and the signature is "
     "refused.", "H",
     ["test_doc_route.RouteFollowsDeviceTests.test_retrofit_device_shows_steps_a_to_g",
      "test_doc_route.RouteFollowsDeviceTests.test_gap_assessment_is_an_effective_device_document_with_that_title",
      "test_doc_route.RouteFollowsDeviceTests.test_greenfield_gates_sit_on_stages_2_4_5_and_6",
      "test_doc_route.RouteFollowsDeviceTests.test_signoff_states_follow_checks_and_approval",
      "test_doc_route.RouteFollowsDeviceTests.test_device_page_draws_the_route_diagram",
      "test_doc_route.RouteFollowsDeviceTests.test_failing_gate_checks_stop_signing_and_alert_the_approver",
      "test_doc_route.RouteFollowsDeviceTests.test_once_checks_pass_the_approver_can_sign",
      "test_doc_route.RouteFollowsDeviceTests.test_gate_open_email_alerts_the_approver_to_failing_checks",
      "test_doc_route.GapAssessmentAndDemoTests.test_signed_gate_shows_who_signed_and_when"],
     []),
    ("URS-118", "Devices", "A gap assessment is a device document of the Gap assessment type, which "
     "step A of the Retrofit route reads. Documents titled \"gap assessment\" still count, and a "
     "document for another device does not. The demo data includes a Retrofit device with its gap "
     "assessment, and one signed Greenfield gate, so the route can be seen working.", "H",
     ["test_doc_route.GapAssessmentAndDemoTests.test_gap_assessment_type_satisfies_step_a",
      "test_doc_route.GapAssessmentAndDemoTests.test_title_only_gap_assessment_still_counts",
      "test_doc_route.GapAssessmentAndDemoTests.test_gap_assessment_of_another_device_does_not_count",
      "test_doc_route.DemoDataRouteTests.test_demo_has_a_retrofit_device_and_a_signed_gate"],
     []),
    ("URS-119", "Devices", "Each task on the My tasks board shows the route step it belongs to: a "
     "gate is its own stage, a document follows its technical file section, a record follows its "
     "type, and training follows its document. The board shows the route's stages in colour, lists "
     "To do and Waiting on others in stage order, and marks work that isn't on the route as not tied "
     "to a stage.", "M",
     ["test_tasks.TaskStageTests.test_a_problem_report_belongs_to_release_and_pms",
      "test_tasks.TaskStageTests.test_a_document_belongs_to_the_step_of_its_technical_file_section",
      "test_tasks.TaskStageTests.test_a_gate_belongs_to_its_own_stage",
      "test_tasks.TaskStageTests.test_retrofit_uses_steps_and_the_gap_assessment_is_step_a",
      "test_tasks.TaskStageTests.test_work_not_on_the_route_has_no_stage",
      "test_tasks.TaskStageTests.test_page_groups_by_stage_and_shows_the_route_legend"],
     []),
    ("URS-120", "Surveillance", "New end users register with their name, email and a password, "
     "and cannot use the surveillance pages until they open the activation link sent to their "
     "email. The link is signed, expires after a set number of days, and works once. An email "
     "already in use is refused.", "H",
     ["test_pms.RegistrationTests.test_registration_creates_an_inactive_account_and_sends_an_activation_link",
      "test_pms.RegistrationTests.test_activation_link_activates_the_account_once",
      "test_pms.RegistrationTests.test_forged_or_expired_activation_link_does_not_activate",
      "test_pms.RegistrationTests.test_registration_refuses_an_email_that_already_exists"],
     []),
    ("URS-121", "Surveillance", "Every surveillance page needs a signed-in account with an "
     "authenticator app (TOTP) set up, and a code from that app completed in the session. This "
     "applies whether the person signed in with a password or through single sign-on. Accounts "
     "without an authenticator are sent to set one up first.", "H",
     ["test_pms.SecondFactorTests.test_surveillance_pages_need_a_signed_in_account",
      "test_pms.SecondFactorTests.test_account_without_an_authenticator_is_sent_to_set_one_up",
      "test_pms.SecondFactorTests.test_account_must_enter_a_code_in_each_session",
      "test_pms.SecondFactorTests.test_signed_in_with_a_code_can_use_the_pages"],
     []),
    ("URS-122", "Surveillance", "Feedback, complaints and suspected incidents are recorded with "
     "the device, the kind of reporter, and the details that kind needs. A suspected incident needs "
     "the date it happened and the date the manufacturer became aware of it; the latest reporting "
     "dates are worked out from the awareness date. Each report gets a reference number.", "H",
     ["test_pms.ReportTests.test_end_user_sends_feedback_and_gets_a_reference",
      "test_pms.ReportTests.test_vigilance_report_needs_the_dates_and_harm"],
     []),
    ("URS-123", "Surveillance", "A reporter sees only their own reports. Only QMS staff see all "
     "reports and change their status; an end user who tries gets a refusal and nothing changes.",
     "H",
     ["test_pms.ReportTests.test_reporter_sees_only_their_own_reports",
      "test_pms.ReportTests.test_qms_staff_triage_a_report",
      "test_pms.ReportTests.test_end_user_cannot_triage"],
     []),
    ("URS-124", "Surveillance", "A reporter can link a report to an issue already raised in an "
     "external bug tracker. GitHub, GitLab, Bitbucket and Jira links show a readable reference; "
     "other https links are kept as given; links that are not https are refused.", "M",
     ["test_pms.LinkTests.test_github_issue_and_pull_request_links_are_recognised",
      "test_pms.LinkTests.test_gitlab_bitbucket_and_jira_links_are_recognised",
      "test_pms.LinkTests.test_other_https_links_are_kept_as_other_trackers",
      "test_pms.LinkTests.test_plain_http_links_are_refused",
      "test_pms.ReportTests.test_reporter_links_an_existing_github_issue"],
     []),
    ("URS-125", "Access", "In production, every page of SAMD_QMS needs a signed-in account with "
     "an authenticator app (TOTP) and a code completed in the session, whether the person signed in "
     "with a password or through single sign-on. The sign-in, sign-out and account-setup pages, the "
     "account request page and health checks stay open. The rule is switched off in development, "
     "staging and tests.", "H",
     ["test_two_factor.QmsTwoFactorTests.test_signed_in_qms_user_without_an_authenticator_is_sent_to_set_one_up",
      "test_two_factor.QmsTwoFactorTests.test_qms_user_with_an_authenticator_must_enter_a_code_each_session",
      "test_two_factor.QmsTwoFactorTests.test_qms_pages_open_once_the_code_is_completed",
      "test_two_factor.QmsTwoFactorTests.test_sign_in_and_sign_out_stay_open_without_a_code",
      "test_two_factor.QmsTwoFactorOffTests.test_qms_pages_do_not_ask_for_a_code_when_the_setting_is_off"],
     []),
]


def automated_test_ids():
    return {t for r in REQUIREMENTS for t in r[4]}
