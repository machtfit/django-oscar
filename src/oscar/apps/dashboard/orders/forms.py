import datetime

from django import forms
from oscar.core.loading import get_model
from django.utils.translation import ugettext_lazy as _
from oscar.apps.address.forms import AbstractAddressForm

from oscar.views.generic import PhoneNumberMixin

Order = get_model('order', 'Order')
OrderNote = get_model('order', 'OrderNote')
ShippingAddress = get_model('order', 'ShippingAddress')
SourceType = get_model('payment', 'SourceType')


class OrderNoteForm(forms.ModelForm):

    class Meta:
        model = OrderNote
        fields = ['message']

    def __init__(self, order, user, *args, **kwargs):
        super(OrderNoteForm, self).__init__(*args, **kwargs)
        self.instance.order = order
        self.instance.user = user


class ShippingAddressForm(PhoneNumberMixin, AbstractAddressForm):

    class Meta:
        model = ShippingAddress
        fields = [
            'title', 'first_name', 'last_name',
            'line1', 'line2', 'line3', 'line4',
            'state', 'postcode', 'country',
            'phone_number', 'notes',
        ]


class OrderStatusForm(forms.Form):
    new_status = forms.ChoiceField(label=_("New order status"), choices=())

    def __init__(self, order, *args, **kwargs):
        super(OrderStatusForm, self).__init__(*args, **kwargs)

        # Set the choices
        choices = [(x, x) for x in order.available_statuses()]
        self.fields['new_status'].choices = choices

    @property
    def has_choices(self):
        return len(self.fields['new_status'].choices) > 0
