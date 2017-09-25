from django.conf.urls import url
from django.contrib.auth.decorators import login_required

from oscar.core.application import Application
from oscar.core.loading import get_class


class CustomerApplication(Application):
    name = 'customer'
    order_history_view = get_class('customer.views', 'OrderHistoryView')

    def get_urls(self):
        urls = [

            # Order history
            url(r'^orders/$',
                login_required(self.order_history_view.as_view()),
                name='order-list')
        ]

        return self.post_process_urls(urls)


application = CustomerApplication()
