from oscar.core.loading import is_model_registered
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