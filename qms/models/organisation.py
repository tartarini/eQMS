"""The organisation running this QMS, and its economic operator roles (EU MDR Art. 2(35)).

An organisation can be the manufacturer of one device and the importer or distributor of
another, so each device records which of the organisation's roles apply to it
(``Device.operator_roles``). The organisation profile lists every role it holds.
"""
from django.db import models

from .core import AuditedModel

# EU MDR economic operators (Art. 2(30)-(34)); the UK framework uses the same roles, with a
# UK Responsible Person in place of the authorised representative.
MANUFACTURER = "manufacturer"
AUTHORISED_REP = "authorised_representative"
IMPORTER = "importer"
DISTRIBUTOR = "distributor"
OPERATOR_ROLES = [
    (MANUFACTURER, "Manufacturer"),
    (AUTHORISED_REP, "Authorised representative"),
    (IMPORTER, "Importer"),
    (DISTRIBUTOR, "Distributor"),
]
OPERATOR_ROLE_LABELS = dict(OPERATOR_ROLES)


def parse_operator_roles(value) -> list:
    """Role codes from a comma-separated string, in the standard order, unknown ones dropped."""
    held = {r.strip() for r in (value or "").split(",") if r.strip()}
    return [code for code, _ in OPERATOR_ROLES if code in held]


def join_operator_roles(codes) -> str:
    codes = set(codes)
    return ", ".join(code for code, _ in OPERATOR_ROLES if code in codes)


class Organisation(AuditedModel):
    """The legal entity running this QMS. There is one; ``Organisation.current()`` returns it."""
    AUDITED = ["name", "address", "srn", "uk_registration", "roles"]

    name = models.CharField("Legal name", max_length=200)
    address = models.TextField("Registered address", blank=True)
    srn = models.CharField("EU Single Registration Number (SRN)", max_length=40, blank=True,
                           help_text="From EUDAMED, e.g. GB-MF-000012345.")
    uk_registration = models.CharField("MHRA registration number", max_length=60, blank=True)
    roles = models.CharField(
        "Economic operator roles", max_length=200, blank=True,
        help_text="Separated by commas: manufacturer, authorised_representative, importer, "
                  "distributor.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "organisation"

    def __str__(self):
        return self.name

    @classmethod
    def current(cls):
        """The organisation profile, or None if nobody has filled it in yet."""
        return cls.objects.order_by("pk").first()

    def role_list(self) -> list:
        return parse_operator_roles(self.roles)

    def role_labels(self) -> list:
        return [OPERATOR_ROLE_LABELS[r] for r in self.role_list()]

    def name_and_address(self) -> str:
        return "\n".join(part for part in (self.name, self.address.strip()) if part)
