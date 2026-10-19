from django import template
from django.templatetags.static import static
from decimal import Decimal, InvalidOperation

from django.utils.html import format_html

register = template.Library()

@register.filter
def get_item(value, key):
    if isinstance(value, dict):
        return value.get(key, '')
    try:
        return getattr(value, key)
    except Exception:
        return ''

@register.filter
def pretty(value):
    if value is None:
        return '—'
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if isinstance(value, (dict, list)):
        return 'Available'
    return value

@register.filter
def ngn(value):
    """Format a numeric API amount as Nigerian naira with grouped thousands."""
    try:
        amount = Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal('0.00')
    return f'₦{amount:,.2f}'


@register.filter
def ngn_kobo(value):
    """Format an integer aggregate in kobo as Nigerian naira."""
    try:
        amount = Decimal(str(value or 0)) / Decimal('100')
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal('0.00')
    return f'₦{amount:,.2f}'


@register.filter
def manager_mask(value):
    """Render a value only in a server-authorized, explicitly revealed manager response."""
    if value is None:
        value = '—'
    return format_html('<span class="manager-sensitive-value">{}</span>', str(value))


@register.simple_tag(takes_context=True)
def private_value(context, value):
    """Mask promotion details unless the one-use authorized reveal was consumed."""
    if value is None:
        value = '—'
    display = str(value) if context.get('promotion_values_revealed') else '***'
    return format_html('<span class="manager-sensitive-value">{}</span>', display)


@register.filter
def humanize_code(value):
    """Render API enum values as readable labels without losing word boundaries."""
    text = str(value or '').strip()
    labels = {
        'UNDER_REVIEW': 'Under review',
        'PROCESSING_UNKNOWN': 'Outcome unknown',
        'PARTIAL_REFUND': 'Partial refund',
        'REFUND': 'Full refund',
        'NO_ADJUSTMENT': 'No financial adjustment',
        'CASE_NOTE_ADDED': 'Private staff note',
        'CASE_MESSAGE_SENT': 'Public case message',
        'CASE_CREATED': 'Case created',
        'CASE_ASSIGNED': 'Case assigned',
        'CASE_CLAIMED': 'Case claimed',
        'CASE_RESOLVED': 'Case resolved',
        'CASE_CLOSED': 'Case closed',
    }
    return labels.get(text.upper(), text.replace('_', ' ').title())


@register.filter
def status_class(value):
    text = str(value or '').upper()
    if any(x in text for x in ('COMPLETED','SUCCEEDED','ACTIVE','VERIFIED','NORMAL','OPEN')):
        return 'ok'
    if any(x in text for x in ('CANCEL','REJECT','FAILED','LOCKED','SUSPENDED','URGENT')):
        return 'bad'
    if any(x in text for x in ('PROCESS','REVIEW','REQUESTED','ACCEPTED','IN_PROGRESS','PENDING')):
        return 'warn'
    return 'neutral'


@register.simple_tag
def page_script(path):
    """Emit the per-page script only when that file exists in the static manifest.

    Pages without a dedicated script must render normally instead of failing with a missing-manifest error.
    """
    if not path:
        return ""
    try:
        url = static(path)
    except ValueError:
        return ""
    return format_html('<script src="{}"></script>', url)
