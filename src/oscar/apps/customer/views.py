from django.shortcuts import redirect
from django.views import generic
from django.core.urlresolvers import reverse_lazy
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from django.contrib.sites.models import get_current_site

from oscar.apps.customer.utils import get_password_reset_url
from oscar.core.loading import (
    get_class, get_classes, get_model)
from oscar.core.compat import get_user_model

PageTitleMixin, RegisterUserMixin = get_classes(
    'customer.mixins', ['PageTitleMixin', 'RegisterUserMixin'])
EmailAuthenticationForm, EmailUserCreationForm, OrderSearchForm = get_classes(
    'customer.forms', ['EmailAuthenticationForm', 'EmailUserCreationForm',
                       'OrderSearchForm'])
PasswordChangeForm = get_class('customer.forms', 'PasswordChangeForm')
ConfirmPasswordForm = get_class('customer.forms', 'ConfirmPasswordForm')
Order = get_model('order', 'Order')

User = get_user_model()


class ChangePasswordView(PageTitleMixin, generic.FormView):
    form_class = PasswordChangeForm
    template_name = 'customer/profile/change_password_form.html'
    page_title = _('Change Password')
    active_tab = 'profile'
    success_url = reverse_lazy('customer:profile-view')

    def get_form_kwargs(self):
        kwargs = super(ChangePasswordView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _("Password updated"))

        ctx = {
            'user': self.request.user,
            'site': get_current_site(self.request),
            'reset_url': get_password_reset_url(self.request.user),
        }
        return redirect(self.get_success_url())

# =============
# Order history
# =============

class OrderHistoryView(PageTitleMixin, generic.ListView):
    """
    Customer order history
    """
    context_object_name = "orders"
    template_name = 'customer/order/order_list.html'
    paginate_by = 20
    model = Order
    form_class = OrderSearchForm
    page_title = _('Order History')
    active_tab = 'orders'

    def get(self, request, *args, **kwargs):
        if 'date_from' in request.GET:
            self.form = self.form_class(self.request.GET)
            if not self.form.is_valid():
                self.object_list = self.get_queryset()
                ctx = self.get_context_data(object_list=self.object_list)
                return self.render_to_response(ctx)
            data = self.form.cleaned_data

            # If the user has just entered an order number, try and look it up
            # and redirect immediately to the order detail page.
            if data['order_number'] and not (data['date_to'] or
                                             data['date_from']):
                try:
                    order = Order.objects.get(
                        number=data['order_number'], user=self.request.user)
                except Order.DoesNotExist:
                    pass
                else:
                    return redirect(
                        'customer:order', order_number=order.number)
        else:
            self.form = self.form_class()
        return super(OrderHistoryView, self).get(request, *args, **kwargs)

    def get_queryset(self):
        qs = self.model._default_manager.filter(user=self.request.user)
        if self.form.is_bound and self.form.is_valid():
            qs = qs.filter(**self.form.get_filters())
        return qs

    def get_context_data(self, *args, **kwargs):
        ctx = super(OrderHistoryView, self).get_context_data(*args, **kwargs)
        ctx['form'] = self.form
        return ctx
