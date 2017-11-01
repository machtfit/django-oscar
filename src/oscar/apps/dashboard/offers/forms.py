from django import forms
from django.utils.translation import ugettext_lazy as _

class OfferSearchForm(forms.Form):
    name = forms.CharField(required=False, label=_("Offer name"))
    is_active = forms.BooleanField(required=False, label=_("Is active?"))
