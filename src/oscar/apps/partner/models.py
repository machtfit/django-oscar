import django

from oscar.core.loading import is_model_registered
from oscar.apps.partner.abstract_models import AbstractStockAlert

__all__ = []


if not is_model_registered('partner', 'StockAlert'):
    class StockAlert(AbstractStockAlert):
        pass

    __all__.append('StockAlert')


if django.VERSION < (1, 7):
    from . import receivers  # noqa
