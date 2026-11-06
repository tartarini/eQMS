from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Email an operational alert to QMS_ALERT_EMAILS (used when a scheduled job fails)."

    def add_arguments(self, parser):
        parser.add_argument("subject")
        parser.add_argument("body", nargs="?", default="")

    def handle(self, *args, subject, body, **options):
        recipients = settings.QMS_ALERT_EMAILS
        if not recipients:
            raise CommandError("QMS_ALERT_EMAILS is not set; nobody to alert.")
        send_mail(f"[SAMD_QMS ALERT] {subject}", body or subject, settings.DEFAULT_FROM_EMAIL,
                  recipients)
        self.stdout.write(f"Alert sent to {', '.join(recipients)}")
