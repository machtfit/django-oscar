from django.conf.urls import url, include

from oscar.core.application import Application
from oscar.core.loading import get_class


class Shop(Application):
    name = None

    catalogue_app = get_class('catalogue.app', 'application')
    customer_app = get_class('customer.app', 'application')
    basket_app = get_class('basket.app', 'application')
    checkout_app = get_class('checkout.app', 'application')
    offer_app = get_class('offer.app', 'application')


    def get_urls(self):
        urls = [
            url(r'^catalogue/', include(self.catalogue_app.urls)),
            url(r'^basket/', include(self.basket_app.urls)),
            url(r'^checkout/', include(self.checkout_app.urls)),
            url(r'^accounts/', include(self.customer_app.urls)),
            url(r'^offers/', include(self.offer_app.urls))]
        return urls


# 'shop' kept for legacy projects - 'application' is a better name
shop = application = Shop()
