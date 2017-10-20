from django.conf.urls import url

from oscar.core.application import Application
from oscar.core.loading import get_class


class OrdersDashboardApplication(Application):
    name = None
    default_permissions = ['is_staff', ]
    permissions_map = {
        'order-detail': (['is_staff'], ['partner.dashboard_access']),
        'order-detail-note': (['is_staff'], ['partner.dashboard_access']),
        'order-line-detail': (['is_staff'], ['partner.dashboard_access']),
        'order-shipping-address': (['is_staff'], ['partner.dashboard_access']),
    }

    order_detail_view = get_class('dashboard.orders.views', 'OrderDetailView')
    shipping_address_view = get_class('dashboard.orders.views',
                                      'ShippingAddressUpdateView')
    line_detail_view = get_class('dashboard.orders.views', 'LineDetailView')

    def get_urls(self):
        urls = [
            url(r'^(?P<number>[-\w]+)/$',
                self.order_detail_view.as_view(), name='order-detail'),
            url(r'^(?P<number>[-\w]+)/notes/(?P<note_id>\d+)/$',
                self.order_detail_view.as_view(), name='order-detail-note'),
            url(r'^(?P<number>[-\w]+)/lines/(?P<line_id>\d+)/$',
                self.line_detail_view.as_view(), name='order-line-detail'),
            url(r'^(?P<number>[-\w]+)/shipping-address/$',
                self.shipping_address_view.as_view(),
                name='order-shipping-address'),
        ]
        return self.post_process_urls(urls)


application = OrdersDashboardApplication()
