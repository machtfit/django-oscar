import json

from django.views.generic import ListView, FormView, DeleteView
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone

from oscar.core.loading import get_classes, get_model
from oscar.views import sort_queryset

ConditionalOffer = get_model('offer', 'ConditionalOffer')
Condition = get_model('offer', 'Condition')
Range = get_model('offer', 'Range')
Product = get_model('catalogue', 'Product')
OrderDiscount = get_model('order', 'OrderDiscount')
Benefit = get_model('offer', 'Benefit')
MetaDataForm, ConditionForm, BenefitForm, RestrictionsForm, OfferSearchForm \
    = get_classes('dashboard.offers.forms',
                  ['MetaDataForm', 'ConditionForm', 'BenefitForm',
                   'RestrictionsForm', 'OfferSearchForm'])


class OfferListView(ListView):
    model = ConditionalOffer
    context_object_name = 'offers'
    template_name = 'dashboard/offers/offer_list.html'
    form_class = OfferSearchForm

    def get_queryset(self):
        qs = self.model._default_manager.exclude(
            offer_type=ConditionalOffer.VOUCHER)
        qs = sort_queryset(qs, self.request,
                           ['name', 'start_datetime', 'end_datetime',
                            'num_applications', 'total_discount'])

        self.description = _("All offers")

        # We track whether the queryset is filtered to determine whether we
        # show the search form 'reset' button.
        self.is_filtered = False
        self.form = self.form_class(self.request.GET)
        if not self.form.is_valid():
            return qs

        data = self.form.cleaned_data

        if data['name']:
            qs = qs.filter(name__icontains=data['name'])
            self.description = _("Offers matching '%s'") % data['name']
            self.is_filtered = True
        if data['is_active']:
            self.is_filtered = True
            now = timezone.now()
            qs = qs.filter(start_datetime__lte=now, end_datetime__gte=now)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super(OfferListView, self).get_context_data(**kwargs)
        ctx['queryset_description'] = self.description
        ctx['form'] = self.form
        ctx['is_filtered'] = self.is_filtered
        return ctx


class OfferDeleteView(DeleteView):
    model = ConditionalOffer
    template_name = 'dashboard/offers/offer_delete.html'
    context_object_name = 'offer'

    def get_success_url(self):
        messages.success(self.request, _("Offer deleted!"))
        return reverse('dashboard:offer-list')


class OfferDetailView(ListView):
    # Slightly odd, but we treat the offer detail view as a list view so the
    # order discounts can be browsed.
    model = OrderDiscount
    template_name = 'dashboard/offers/offer_detail.html'
    context_object_name = 'order_discounts'

    def dispatch(self, request, *args, **kwargs):
        self.offer = get_object_or_404(ConditionalOffer, pk=kwargs['pk'])
        return super(OfferDetailView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if 'suspend' in request.POST:
            return self.suspend()
        elif 'unsuspend' in request.POST:
            return self.unsuspend()

    def suspend(self):
        if self.offer.is_suspended:
            messages.error(self.request, _("Offer is already suspended"))
        else:
            self.offer.suspend()
            messages.success(self.request, _("Offer suspended"))
        return HttpResponseRedirect(
            reverse('dashboard:offer-detail', kwargs={'pk': self.offer.pk}))

    def unsuspend(self):
        if not self.offer.is_suspended:
            messages.error(
                self.request,
                _("Offer cannot be reinstated as it is not currently "
                  "suspended"))
        else:
            self.offer.unsuspend()
            messages.success(self.request, _("Offer reinstated"))
        return HttpResponseRedirect(
            reverse('dashboard:offer-detail', kwargs={'pk': self.offer.pk}))

    def get_queryset(self):
        return self.model.objects.filter(offer_id=self.offer.pk)

    def get_context_data(self, **kwargs):
        ctx = super(OfferDetailView, self).get_context_data(**kwargs)
        ctx['offer'] = self.offer
        return ctx

    def render_to_response(self, context):
        return super(OfferDetailView, self).render_to_response(context)
