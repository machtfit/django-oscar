from django.conf.urls import url
from django.contrib.auth.decorators import login_required

from oscar.core.application import Application
from oscar.core.loading import get_class


class CustomerApplication(Application):
    name = 'customer'
    order_history_view = get_class('customer.views', 'OrderHistoryView')

    change_password_view = get_class('customer.views', 'ChangePasswordView')

    def get_urls(self):
        urls = [

            url(r'^change-password/$',
                login_required(self.change_password_view.as_view()),
                name='change-password'),


            # Order history
            url(r'^orders/$',
                login_required(self.order_history_view.as_view()),
                name='order-list')
        ]

        return self.post_process_urls(urls)


application = CustomerApplication()
