from django.conf.urls import url

from oscar.core.application import Application
from oscar.core.loading import get_class


class OrdersDashboardApplication(Application):
    name = None
    default_permissions = ['is_staff', ]
    permissions_map = {
        'order-shipping-address': (['is_staff'], ['partner.dashboard_access']),
    }

    shipping_address_view = get_class('dashboard.orders.views',
                                      'ShippingAddressUpdateView')

    def get_urls(self):
        urls = [
            url(r'^(?P<number>[-\w]+)/shipping-address/$',
                self.shipping_address_view.as_view(),
                name='order-shipping-address'),
        ]
        return self.post_process_urls(urls)


application = OrdersDashboardApplication()
