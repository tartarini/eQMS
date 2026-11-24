from django.core.management.base import BaseCommand

from qms.notifications import dispatch_pending


class Command(BaseCommand):
    help = ("Send queued notifications that are still waiting (for example after a failed "
            "email). The scheduler runs this every minute; it is safe to run by hand.")

    def handle(self, *args, **options):
        sent = dispatch_pending()
        self.stdout.write(self.style.SUCCESS(f"{sent} notification(s) sent."))
