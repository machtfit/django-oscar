from oscar.core.loading import is_model_registered
from oscar.apps.order.abstract_models import *  # noqa
from oscar.apps.address.abstract_models import (AbstractShippingAddress,
                                                AbstractBillingAddress)

__all__ = []


if not is_model_registered('order', 'ShippingAddress'):
    class ShippingAddress(AbstractShippingAddress):
        pass

    __all__.append('ShippingAddress')


if not is_model_registered('order', 'BillingAddress'):
    class BillingAddress(AbstractBillingAddress):
        pass

    __all__.append('BillingAddress')


if not is_model_registered('order', 'Line'):
    class Line(AbstractLine):
        pass

    __all__.append('Line')
