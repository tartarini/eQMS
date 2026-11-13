"""Two-factor sign-in across SAMD_QMS when QMS_TWO_FACTOR is on (production)."""
from django.test import TestCase, override_settings
from django.urls import reverse

from .test_pms import end_user, sign_in, with_authenticator


@override_settings(QMS_TWO_FACTOR=True)
class QmsTwoFactorTests(TestCase):
    def test_signed_in_qms_user_without_an_authenticator_is_sent_to_set_one_up(self):
        user = end_user("qa_two")
        sign_in(self.client, user, second_factor=False)
        response = self.client.get(reverse("qms:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("mfa_activate_totp")), response.url)

    def test_qms_user_with_an_authenticator_must_enter_a_code_each_session(self):
        user = end_user("qa_three")
        with_authenticator(user)
        sign_in(self.client, user, second_factor=False)
        response = self.client.get(reverse("qms:dashboard"))
        self.assertTrue(response.url.startswith(reverse("mfa_reauthenticate")), response.url)

    def test_qms_pages_open_once_the_code_is_completed(self):
        user = end_user("qa_four")
        with_authenticator(user)
        sign_in(self.client, user)
        self.assertNotEqual(self.client.get(reverse("qms:dashboard")).status_code, 302)

    def test_sign_in_and_sign_out_stay_open_without_a_code(self):
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)
        user = end_user("qa_five")
        sign_in(self.client, user, second_factor=False)
        self.assertEqual(self.client.get(reverse("socialaccount_connections")).status_code, 200)


class QmsTwoFactorOffTests(TestCase):
    """Development, staging and the test suite: QMS sign-in is unchanged."""

    @override_settings(QMS_TWO_FACTOR=False)
    def test_qms_pages_do_not_ask_for_a_code_when_the_setting_is_off(self):
        user = end_user("qa_six")
        sign_in(self.client, user, second_factor=False)
        response = self.client.get(reverse("qms:dashboard"))
        self.assertFalse(getattr(response, "url", "").startswith(reverse("mfa_activate_totp")))
