import django

from oscar.core.loading import is_model_registered
from oscar.apps.customer import abstract_models

__all__ = []


if not is_model_registered('customer', 'Email'):
    class Email(abstract_models.AbstractEmail):
        pass

    __all__.append('Email')

if not is_model_registered('customer', 'Notification'):
    class Notification(abstract_models.AbstractNotification):
        pass

    __all__.append('Notification')


if django.VERSION < (1, 7):
    from .receivers import *  # noqa
    from .alerts import receivers  # noqa
