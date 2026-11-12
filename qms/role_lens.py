"""Acting as one role.

A person who holds several roles can choose one in the header ("Acting as"). While they do,
the app works as that role only: every role check and the functions listed on the dashboard
use just that role. The choice can narrow what a person can do but never add a role they do
not hold. It is kept in the session, and dropped if the role is no longer held.
"""
from . import workflow as wf
from .models import GATES_BY_ROUTE
from .roles import active_role, unlensed_all_roles

SESSION_ROLE_KEY = "qms_active_role"


class ActiveRoleMiddleware:
    """Puts the chosen role on the signed-in user for this request (see qms.roles)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        session = getattr(request, "session", None)
        if user is not None and session is not None and user.is_authenticated:
            chosen = session.get(SESSION_ROLE_KEY)
            if chosen:
                if chosen in unlensed_all_roles(user):
                    user.active_role = chosen
                else:
                    session.pop(SESSION_ROLE_KEY, None)
        return self.get_response(request)


def role_options(user) -> list:
    """The roles the person really holds, in the standard order."""
    held = unlensed_all_roles(user)
    return [r for r in wf.ROLES if r in held]


def role_functions(role) -> list:
    """What a role can do, as (heading, [items]). Worked out from the workflow and the approver
    gates, so it stays in step with what the app enforces."""
    sections = []
    steps = []
    for code, label in wf.RECORD_TYPES:
        for t in wf.all_transitions(code):
            if role in t.roles:
                steps.append(f"{label}: {t.label}")
    if steps:
        sections.append(("Quality records", steps))
    if role == wf.QA:
        sections.append(("Documents, hazards and technical files", [
            "Approve document versions, and make approved versions effective",
            "Approve hazards and their risk controls",
            "Approve technical file builds"]))
    if role in wf.TEAM_MANAGERS:
        sections.append(("Team and access", [
            "Invite people to your devices, and change or remove team members",
            "Review account requests"]))
    gates = [f"Stage {stage}: {name} ({route.capitalize()} route)"
             for route, route_gates in GATES_BY_ROUTE.items()
             for stage, name, gate_role in route_gates if gate_role == role]
    if gates:
        sections.append(("Approver gates", gates))
    return sections
