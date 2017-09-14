from django.conf.urls import url

from oscar.core.application import Application
from oscar.core.loading import get_class


class CatalogueApplication(Application):
    name = 'catalogue'
    detail_view = get_class('catalogue.views', 'ProductDetailView')
    range_view = get_class('offer.views', 'RangeDetailView')

    def get_urls(self):
        urlpatterns = super(CatalogueApplication, self).get_urls()
        urlpatterns += [
            url(r'^(?P<product_slug>[\w-]*)_(?P<pk>\d+)/$',
                self.detail_view.as_view(), name='detail'),
            url(r'^ranges/(?P<slug>[\w-]+)/$',
                self.range_view.as_view(), name='range')]
        return self.post_process_urls(urlpatterns)


application = CatalogueApplication()
