from django.core import validators
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _


def non_whitespace(value):
    stripped = value.strip()
    if not stripped:
        raise ValidationError(
            _("This field is required"))
    return stripped


