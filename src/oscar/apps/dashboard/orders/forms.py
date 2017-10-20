import datetime

from django import forms
from oscar.core.loading import get_model
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import pgettext_lazy
from oscar.apps.address.forms import AbstractAddressForm

from oscar.views.generic import PhoneNumberMixin

Order = get_model('order', 'Order')
OrderNote = get_model('order', 'OrderNote')
ShippingAddress = get_model('order', 'ShippingAddress')
SourceType = get_model('payment', 'SourceType')


class OrderStatsForm(forms.Form):
    date_from = forms.DateField(
        required=False, label=pgettext_lazy(u"start date", u"From"))
    date_to = forms.DateField(
        required=False, label=pgettext_lazy(u"end date", u"To"))

    _filters = _description = None

    def _determine_filter_metadata(self):
        self._filters = {}
        self._description = _('All orders')
        if self.errors:
            return

        date_from = self.cleaned_data['date_from']
        date_to = self.cleaned_data['date_to']
        if date_from and date_to:
            # We want to include end date so we adjust the date we use with the
            # 'range' function.
            self._filters = {'date_placed__range':
                             [date_from, date_to + datetime.timedelta(days=1)]}
            self._description = _('Orders placed between %(date_from)s and'
                                  ' %(date_to)s') % {
                'date_from': date_from,
                'date_to': date_to}
        elif date_from and not date_to:
            self._filters = {'date_placed__gte': date_from}
            self._description = _('Orders placed since %s') % (date_from,)
        elif not date_from and date_to:
            self._filters = {'date_placed__lte': date_to}
            self._description = _('Orders placed until %s') % (date_to,)
        else:
            self._filters = {}
            self._description = _('All orders')

    def get_filters(self):
        if self._filters is None:
            self._determine_filter_metadata()
        return self._filters

    def get_filter_description(self):
        if self._description is None:
            self._determine_filter_metadata()
        return self._description


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
