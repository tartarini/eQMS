"""SAMD_QMS: quality management system for software medical devices (Django app).

Runs standalone (the ``config`` project in this repository) or inside another Django project;
see docs/embedding.md.
"""

# Release of the qms and pms apps, as installed by pip. A release tag vX.Y.Z must match it
# (checked by CI), so a host project that pins `samd-qms @ git+...@vX.Y.Z` reports the same
# version that was validated.
__version__ = "1.0.0.dev0"
