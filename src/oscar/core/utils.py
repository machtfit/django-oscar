from __future__ import absolute_import  # for logging import below

from django.conf import settings


def get_default_currency():
    """
    For use as the default value for currency fields.  Use of this function
    prevents Django's core migration engine from interpreting a change to
    OSCAR_DEFAULT_CURRENCY as something it needs to generate a migration for.
    """
    return settings.OSCAR_DEFAULT_CURRENCY
