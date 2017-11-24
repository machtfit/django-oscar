from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _


@python_2_unicode_compatible
class AbstractStockAlert(models.Model):
    """
    A stock alert. E.g. used to notify users when a product is 'back in stock'.
    """
    stockrecord = models.ForeignKey(
        'partner.StockRecord', related_name='alerts',
        verbose_name=_("Stock Record"))
    threshold = models.PositiveIntegerField(_("Threshold"))
    OPEN, CLOSED = "Open", "Closed"
    status_choices = (
        (OPEN, _("Open")),
        (CLOSED, _("Closed")),
    )
    status = models.CharField(_("Status"), max_length=128, default=OPEN,
                              choices=status_choices)
    date_created = models.DateTimeField(_("Date Created"), auto_now_add=True)
    date_closed = models.DateTimeField(_("Date Closed"), blank=True, null=True)

    def close(self):
        self.status = self.CLOSED
        self.save()
    close.alters_data = True

    def __str__(self):
        return _('<stockalert for "%(stock)s" status %(status)s>') \
            % {'stock': self.stockrecord, 'status': self.status}

    class Meta:
        abstract = True
        app_label = 'partner'
        ordering = ('-date_created',)
        verbose_name = _('Stock alert')
        verbose_name_plural = _('Stock alerts')
