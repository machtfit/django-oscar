from oscar.core.loading import get_model
from oscar.apps.address.forms import AbstractAddressForm
from oscar.views.generic import PhoneNumberMixin

Country = get_model('address', 'Country')
BillingAddress = get_model('order', 'BillingAddress')


class BillingAddressForm(PhoneNumberMixin, AbstractAddressForm):

    def __init__(self, *args, **kwargs):
        super(BillingAddressForm, self).__init__(*args, **kwargs)
        self.set_country_queryset()

    def set_country_queryset(self):
        self.fields['country'].queryset = Country._default_manager.all()

    class Meta:
        model = BillingAddress
        fields = [
            'title', 'first_name', 'last_name',
            'line1', 'line2', 'line3', 'line4',
            'state', 'postcode', 'country',
        ]
