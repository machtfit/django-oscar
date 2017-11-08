from django.conf.urls import url, include

from oscar.core.application import Application
from oscar.core.loading import get_class


class DashboardApplication(Application):
    name = 'dashboard'

    index_view = get_class('dashboard.views', 'IndexView')
    users_app = get_class('dashboard.users.app', 'application')
    catalogue_app = get_class('dashboard.catalogue.app', 'application')
    offers_app = get_class('dashboard.offers.app', 'application')

    def get_urls(self):
        urls = [
            url(r'^catalogue/', include(self.catalogue_app.urls)),
            url(r'^users/', include(self.users_app.urls)),
            url(r'^offers/', include(self.offers_app.urls)),
        ]
        return self.post_process_urls(urls)


application = DashboardApplication()
