
from django.core.exceptions import ImproperlyConfigured
from django.db.models.fields import CharField
from django.db.models import SubfieldBase
from django.utils import six
from django.utils.translation import ugettext_lazy as _

import oscar.core.phonenumber as phonenumber


class UppercaseCharField(six.with_metaclass(SubfieldBase, CharField)):
    """
    A simple subclass of ``django.db.models.fields.CharField`` that
    restricts all text to be uppercase.

    Defined with the with_metaclass helper so that to_python is called
    https://docs.djangoproject.com/en/1.6/howto/custom-model-fields/#the-subfieldbase-metaclass  # NOQA
    """

    def to_python(self, value):
        val = super(UppercaseCharField, self).to_python(value)
        if isinstance(val, six.string_types):
            return val.upper()
        else:
            return val


class PhoneNumberField(six.with_metaclass(SubfieldBase, CharField)):
    """
    An international phone number.

    * Validates a wide range of phone number formats
    * Displays it nicely formatted

    Notes
    -----
    This field is based on work in django-phonenumber-field
    https://github.com/maikhoepfel/django-phonenumber-field/

    See ``oscar/core/phonenumber.py`` for the relevant copyright and
    permission notice.
    """

    default_validators = [phonenumber.validate_international_phonenumber]

    description = _("Phone number")

    def __init__(self, *args, **kwargs):
        # There's no useful distinction between '' and None for a phone
        # number. To avoid running into issues that are similar to what
        # NullCharField tries to solve, we just forbid settings null=True.
        if kwargs.get('null', False):
            raise ImproperlyConfigured(
                "null=True is not supported on PhoneNumberField")
        # Set a default max_length.
        kwargs['max_length'] = kwargs.get('max_length', 128)
        super(PhoneNumberField, self).__init__(*args, **kwargs)

    def get_prep_value(self, value):
        """
        Returns field's value prepared for saving into a database.
        """
        value = phonenumber.to_python(value)
        if value is None:
            return u''
        return value.as_e164 if value.is_valid() else value.raw_input

    def to_python(self, value):
        return phonenumber.to_python(value)

    def value_to_string(self, obj):
        """
        Used when the field is serialized. See Django docs.
        """
        value = self._get_val_from_obj(obj)
        return self.get_prep_value(value)

    def deconstruct(self):
        """
        deconstruct() is needed by Django's migration framework.
        """
        name, path, args, kwargs = super(PhoneNumberField, self).deconstruct()
        # Delete kwargs at default value.
        if self.max_length == 128:
            del kwargs['max_length']
        return name, path, args, kwargs
