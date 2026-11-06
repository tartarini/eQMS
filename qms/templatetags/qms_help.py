"""The "?" help icon shown beside form fields. Text comes from ``qms.help.FIELD_HELP``."""
import uuid

from django import template
from django.utils.html import format_html

from ..help import field_help, group_field_help

register = template.Library()


@register.simple_tag
def help_icon(bound_field):
    """A button that opens a popover explaining the field, with a link to the full guide.

    Uses the HTML popover attribute, so it works without JavaScript and closes with Esc or a
    click outside. Renders nothing for fields with no registered help (a test forbids that).
    """
    return _icon(field_help(bound_field.form, bound_field.name))


@register.simple_tag
def help_for(group, field_name):
    """Help icon for a field written as plain HTML: {% help_for "sign" "password" %}."""
    return _icon(group_field_help(group, field_name))


def _icon(found):
    if not found:
        return ""
    label, text, url = found
    pop_id = f"help-{uuid.uuid4().hex[:10]}"
    return format_html(
        '<button type="button" class="help-icon" popovertarget="{id}" '
        'aria-label="Help: {label}" title="Help: {label}">?</button>'
        '<span id="{id}" class="help-pop" popover role="note">'
        '<strong>{label}</strong><span class="help-body">{text}</span>'
        '<a href="{url}" target="_blank" rel="noopener">More in the guide</a></span>',
        id=pop_id, label=label, text=text, url=url)
