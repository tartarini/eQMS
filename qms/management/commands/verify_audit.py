from django.core.management.base import BaseCommand, CommandError

from qms.models import AuditEvent, verify_audit_chain


class Command(BaseCommand):
    help = "Verify the audit trail hash chain. Exits non-zero if any event was altered."

    def handle(self, *args, **options):
        ok, bad_id = verify_audit_chain()
        total = AuditEvent.objects.count()
        if not ok:
            raise CommandError(f"Audit chain broken at event {bad_id} (of {total}).")
        self.stdout.write(self.style.SUCCESS(f"Audit chain intact: {total} events verified."))
