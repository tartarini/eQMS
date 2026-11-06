from django.core.management.base import BaseCommand

from qms.notifications import daily_reminders
from qms.services import sync_training


class Command(BaseCommand):
    help = ("Daily job: assign any missing training, then email each person a digest of overdue "
            "and due-soon items (records, training, document reviews, suppliers, SOUP).")

    def handle(self, *args, **options):
        assigned = sync_training()
        sent = daily_reminders()
        self.stdout.write(self.style.SUCCESS(
            f"{len(assigned)} training assignment(s) created; {sent} reminder email(s) queued."))
