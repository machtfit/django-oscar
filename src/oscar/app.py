from django.conf.urls import url, include

from oscar.core.application import Application
from oscar.core.loading import get_class


class Shop(Application):
    name = None

    customer_app = get_class('customer.app', 'application')

    def get_urls(self):
        urls = [
            url(r'^accounts/', include(self.customer_app.urls))]
        return urls


# 'shop' kept for legacy projects - 'application' is a better name
shop = application = Shop()
