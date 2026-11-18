"""Central minimum individual price rule for the artisan-facing forms.

Every actual individual charge an artisan enters or submits anywhere in the
Artisan Market must be at least ₦100.00. This module mirrors the backend's
``core.pricing`` so the browser, the page back-end and the API agree on the
rule and on the message shown when it is broken.

* Zero is only ever accepted for an optional charge that is not applied
  (``allow_zero=True``) — e.g. transport when no transport is charged.
* Anything else below ₦100.00 is rejected, never silently rounded up.
* Calculation uses ``Decimal`` quantized to two places; no floats.
"""

from decimal import Decimal, InvalidOperation

MIN_INDIVIDUAL_PRICE = Decimal("100.00")
MIN_INDIVIDUAL_PRICE_MESSAGE = (
    "The minimum permitted price for an item or service is ₦100.00."
)


def parse_amount(value):
    """Parse a form amount to Decimal, or None when unparseable/blank."""
    text = str(value if value is not None else "").strip().replace(",", "")
    if not text:
        return None
    try:
        parsed = Decimal(text)
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not parsed.is_finite():
        return None
    return parsed.quantize(Decimal("0.01"))


def min_price_error(value, *, allow_zero=False, blank_means_error=False):
    """Return the error message for an amount, or None when it is valid.

    ``allow_zero`` accepts exactly 0.00 as "not charged". ``blank_means_error``
    treats an empty input as invalid (used for required charges).
    """
    parsed = parse_amount(value)
    if parsed is None:
        return MIN_INDIVIDUAL_PRICE_MESSAGE if blank_means_error else None
    if allow_zero and parsed == Decimal("0.00"):
        return None
    if parsed < MIN_INDIVIDUAL_PRICE:
        return MIN_INDIVIDUAL_PRICE_MESSAGE
    return None


def check_pricing_fields(fields):
    """Validate a mapping of {field_name: (value, allow_zero)}.

    Returns {field_name: message} for every field that violates the rule.
    """
    errors = {}
    for name, (value, allow_zero) in fields.items():
        message = min_price_error(value, allow_zero=allow_zero)
        if message:
            errors[name] = message
    return errors
