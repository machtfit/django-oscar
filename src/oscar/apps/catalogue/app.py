from oscar.core.application import Application


class CatalogueApplication(Application):
    name = 'catalogue'


    def get_urls(self):
        urlpatterns = super(CatalogueApplication, self).get_urls()
        return self.post_process_urls(urlpatterns)


application = CatalogueApplication()
