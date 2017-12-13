from oscar.core.loading import is_model_registered
from oscar.apps.address.abstract_models import AbstractCountry

__all__ = []


if not is_model_registered('address', 'Country'):
    class Country(AbstractCountry):
        pass

    __all__.append('Country')
