#!/usr/bin/env python
"""A minimal host project that runs SAMD_QMS as an installed app, as a platform would.

CI copies this folder out of the repository, installs the built samd-qms wheel and runs the
whole SAMD_QMS test suite here (see docs/embedding.md):

    python manage.py check && python manage.py test qms platform_host
"""
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "platform_host.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
