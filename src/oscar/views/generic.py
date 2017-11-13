from django import forms
from django.core import validators
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

import phonenumbers

from oscar.core.phonenumber import PhoneNumber


class PhoneNumberMixin(object):
    """
    Validation mixin for forms with a phone number, and optionally a country.
    It tries to validate the phone number, and on failure tries to validate it
    using a hint (the country provided), and treating it as a local number.
    """

    phone_number = forms.CharField(max_length=32, required=False)

    def get_country(self):
        # If the form data contains valid country information, we use that.
        if hasattr(self, 'cleaned_data') and 'country' in self.cleaned_data:
            return self.cleaned_data['country']
        # Oscar hides the field if there's only one country. Then (and only
        # then!) can we consider a country on the model instance.
        elif 'country' not in self.fields and hasattr(
                self.instance, 'country'):
            return self.instance.country

    def get_region_code(self, country):
        return country.iso_3166_1_a2

    def clean_phone_number(self):
        number = self.cleaned_data['phone_number']

        # empty
        if number in validators.EMPTY_VALUES:
            return None

        # Check for an international phone format
        try:
            phone_number = PhoneNumber.from_string(number)
        except phonenumbers.NumberParseException:
            # Try hinting with the shipping country
            country = self.get_country()
            region_code = self.get_region_code(country)

            if not region_code:
                # There is no shipping country, not a valid international
                # number
                raise ValidationError(
                    _(u'This is not a valid international phone format.'))

            # The PhoneNumber class does not allow specifying
            # the region. So we drop down to the underlying phonenumbers
            # library, which luckily allows parsing into a PhoneNumber
            # instance
            try:
                phone_number = PhoneNumber.from_string(
                    number, region=region_code)
                if not phone_number.is_valid():
                    raise ValidationError(
                        _(u'This is not a valid local phone format for %s.')
                        % country)
            except phonenumbers.NumberParseException:
                # Not a valid local or international phone number
                raise ValidationError(
                    _(u'This is not a valid local or international phone'
                      u' format.'))

        return phone_number
