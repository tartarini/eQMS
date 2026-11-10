from datetime import date

from django.core.management.base import BaseCommand

from qms.retention import retention_items


class Command(BaseCommand):
    help = ("List closed records and withdrawn documents with the end of their retention period. "
            "Nothing is deleted: this report supports the organisation's disposition decisions.")

    def add_arguments(self, parser):
        parser.add_argument("--within-days", type=int, default=None,
                            help="Only items whose retention ends within this many days, or has "
                                 "already ended.")

    def handle(self, *args, **options):
        rows = retention_items(within_days=options["within_days"], today=date.today())
        if not rows:
            self.stdout.write("No items in scope.")
            return
        self.stdout.write(f"{'Kind':<9}{'Reference':<12}{'Device':<10}{'From':<12}"
                          f"{'Retain until':<14}Note")
        for r in rows:
            note = "" if r["lifetime_defined"] else "Set the device's expected lifetime"
            self.stdout.write(f"{r['kind']:<9}{r['ref']:<12}{r['device']:<10}"
                              f"{r['from'].isoformat():<12}{r['until'].isoformat():<14}{note}")
