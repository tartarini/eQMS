from django.core.management.base import BaseCommand

from qms.services import generate_pms_activities


class Command(BaseCommand):
    help = "Create PMS Activity records for schedules due soon. Safe to run daily (e.g. cron)."

    def add_arguments(self, parser):
        parser.add_argument("--horizon-days", type=int, default=None,
                            help="Create activities due within this many days (default: setting)")

    def handle(self, *args, horizon_days=None, **options):
        created = generate_pms_activities(horizon_days=horizon_days)
        for r in created:
            self.stdout.write(f"Created {r.ref}: {r.title}")
        self.stdout.write(self.style.SUCCESS(f"{len(created)} PMS activities created."))
