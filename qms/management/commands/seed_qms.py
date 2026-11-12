from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from qms import workflow as wf
from qms.models import Device
from qms.services import setup_device_pms


class Command(BaseCommand):
    help = ("Create QMS roles, and the standard PMS schedule for any device that lacks it. "
            "Use --demo for demo users (never in production).")

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true",
                            help="Also create demo users engineer_person/qa_person/cso_person (password: demo-pass-123)")

    def handle(self, *args, demo=False, **options):
        record_perms = Permission.objects.filter(content_type__app_label="qms")
        for name in wf.ROLES + (wf.ALL_DEVICES, wf.QMS_ADMIN):
            group, created = Group.objects.get_or_create(name=name)
            if name == wf.QA:
                group.permissions.set(record_perms)
            self.stdout.write(f"{'Created' if created else 'Found'} group {name}")

        for device in Device.objects.filter(active=True):
            created = setup_device_pms(device)
            if created:
                self.stdout.write(f"Scheduled {len(created)} PMS activities for {device}")

        if demo:
            User = get_user_model()
            for username, role, staff in [("engineer_person", wf.ENGINEER, False), ("qa_person", wf.QA, True),
                                          ("cso_person", wf.CLINICAL_SAFETY, False)]:
                user, created = User.objects.get_or_create(
                    username=username, defaults={"first_name": role, "is_staff": staff,
                                                 "email": f"{username}@example.org"})
                if created:
                    user.set_password("demo-pass-123")
                    user.save()
                if role == wf.QA:  # organisation-wide QA; others get roles per device team
                    user.groups.add(Group.objects.get(name=role))
                self.stdout.write(f"{'Created' if created else 'Found'} demo user {username}")
        self.stdout.write(self.style.SUCCESS("Seed complete."))
