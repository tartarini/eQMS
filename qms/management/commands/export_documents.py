"""Keep a git repository in step with the controlled documents, and/or write a zip archive.

    python manage.py export_documents --git /srv/qms-documents            # commit changes
    python manage.py export_documents --git /srv/qms-documents --push    # and push them
    python manage.py export_documents --zip /srv/qms-documents.zip

The repository must already be cloned. Only files that differ from the QMS are written, and
a commit is made only when something changed (see qms.doc_exchange.sync_git).
"""
import subprocess

from django.core.management.base import BaseCommand, CommandError

from qms import doc_exchange


class Command(BaseCommand):
    help = "Keep a git clone of the controlled documents in step with the QMS, and/or write a zip."

    def add_arguments(self, parser):
        parser.add_argument("--git", help="Local clone of the documents repository.")
        parser.add_argument("--push", action="store_true",
                            help="Push the commit to the clone's remote.")
        parser.add_argument("--zip", help="Zip archive to write.")

    def handle(self, *args, **options):
        if not options["git"] and not options["zip"]:
            raise CommandError("Give --git, --zip or both.")
        if options["git"]:
            try:
                result = doc_exchange.sync_git(options["git"], push=options["push"])
            except (ValueError, subprocess.CalledProcessError) as exc:
                raise CommandError(f"Documents repository sync failed: {exc}") from exc
            self.stdout.write(self.style.SUCCESS(
                f"{options['git']}: {result['written']} written, {result['unchanged']} unchanged, "
                f"{result['removed']} removed; "
                + ("committed" if result["committed"] else "no changes to commit")
                + ("; pushed" if result["pushed"] else "") + "."))
        if options["zip"]:
            with open(options["zip"], "wb") as fh:
                fh.write(doc_exchange.export_zip())
            self.stdout.write(self.style.SUCCESS(f"{options['zip']} written."))
