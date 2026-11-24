from getpass import getpass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from qms import workflow as wf
from qms.models import AuditEvent


class Command(BaseCommand):
    help = (f"Create a QMS admin account. A QMS admin manages {settings.QMS_PRODUCT_NAME} overall "
            "and is the only one "
            "who can appoint Device admins. The password is asked for at a prompt. This does not "
            "give access to the Django admin site (that needs a superuser: createsuperuser).")

    def add_arguments(self, parser):
        parser.add_argument("username", help="Sign-in name for the new account.")
        parser.add_argument("--email", required=True,
                            help="Email address. Must not belong to another account.")
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")

    def handle(self, *args, username, email, first_name, last_name, **options):
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise CommandError(f"An account named {username} already exists.")
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(f"Another account already uses {email}.")

        password = getpass("Password for the new QMS admin: ")
        if getpass("Password again: ") != password:
            raise CommandError("The passwords do not match. No account was created.")
        candidate = User(username=username, email=email, first_name=first_name,
                         last_name=last_name)
        try:
            validate_password(password, candidate)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc

        with transaction.atomic():
            user = User.objects.create_user(username, email, password, first_name=first_name,
                                            last_name=last_name)
            group, _ = Group.objects.get_or_create(name=wf.QMS_ADMIN)
            user.groups.add(group)
            AuditEvent.log("security", comment="QMS admin account created from the command line",
                           changes={"account": [None, username],
                                    "group": [None, wf.QMS_ADMIN]})
        self.stdout.write(self.style.SUCCESS(
            f"Created QMS admin {username}. They can sign in with the password just set."))
