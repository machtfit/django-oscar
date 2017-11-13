import json

from django import forms
from django.core import validators
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.utils.encoding import smart_str
from django.contrib import messages
from django.http import HttpResponse
from django.utils import six
from django.utils.six.moves import map
from django.utils.translation import ugettext_lazy as _
from django.views.generic.base import View

import phonenumbers

from oscar.core.utils import safe_referrer
from oscar.core.phonenumber import PhoneNumber


class BulkEditMixin(object):
    """
    Mixin for views that have a bulk editing facility.  This is normally in the
    form of tabular data where each row has a checkbox.  The UI allows a number
    of rows to be selected and then some 'action' to be performed on them.
    """
    action_param = 'action'

    # Permitted methods that can be used to act on the selected objects
    actions = None
    checkbox_object_name = None

    def get_checkbox_object_name(self):
        if self.checkbox_object_name:
            return self.checkbox_object_name
        return smart_str(self.model._meta.object_name.lower())

    def get_error_url(self, request):
        return safe_referrer(request, '.')

    def get_success_url(self, request):
        return safe_referrer(request, '.')

    def post(self, request, *args, **kwargs):
        # Dynamic dispatch pattern - we forward POST requests onto a method
        # designated by the 'action' parameter.  The action has to be in a
        # whitelist to avoid security issues.
        action = request.POST.get(self.action_param, '').lower()
        if not self.actions or action not in self.actions:
            messages.error(self.request, _("Invalid action"))
            return redirect(self.get_error_url(request))

        ids = request.POST.getlist(
            'selected_%s' % self.get_checkbox_object_name())
        ids = list(map(int, ids))
        if not ids:
            messages.error(
                self.request,
                _("You need to select some %ss")
                % self.model._meta.verbose_name_plural)
            return redirect(self.get_error_url(request))

        objects = self.get_objects(ids)
        return getattr(self, action)(request, objects)

    def get_objects(self, ids):
        object_dict = self.get_object_dict(ids)
        # Rearrange back into the original order
        return [object_dict[id] for id in ids]

    def get_object_dict(self, ids):
        return self.get_queryset().in_bulk(ids)


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
