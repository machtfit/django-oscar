from oscar.core.loading import get_model
from oscar.apps.address.forms import AbstractAddressForm

from oscar.views.generic import PhoneNumberMixin

ShippingAddress = get_model('order', 'ShippingAddress')




class ShippingAddressForm(PhoneNumberMixin, AbstractAddressForm):

    class Meta:
        model = ShippingAddress
        fields = [
            'title', 'first_name', 'last_name',
            'line1', 'line2', 'line3', 'line4',
            'state', 'postcode', 'country',
            'phone_number', 'notes',
        ]


