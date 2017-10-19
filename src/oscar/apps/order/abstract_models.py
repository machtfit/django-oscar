from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _, pgettext_lazy
from django.utils.datastructures import SortedDict

from oscar.models.fields import AutoSlugField
from . import exceptions


@python_2_unicode_compatible
class AbstractLine(models.Model):
    """
    An order line
    """
    order = models.ForeignKey(
        'order.Order', related_name='lines', verbose_name=_("Order"))

    # PARTNER INFORMATION
    # -------------------
    # We store the partner and various detail their SKU and the title for cases
    # where the product has been deleted from the catalogue (but we still need
    # the data for reporting).  We also store the partner name in case the
    # partner gets deleted at a later date.

    partner = models.ForeignKey(
        'partner.Partner', related_name='order_lines', blank=True, null=True,
        on_delete=models.SET_NULL, verbose_name=_("Partner"))
    partner_name = models.CharField(
        _("Partner name"), max_length=128, blank=True)
    partner_sku = models.CharField(_("Partner SKU"), max_length=128)

    # A line reference is the ID that a partner uses to represent this
    # particular line (it's not the same as a SKU).
    partner_line_reference = models.CharField(
        _("Partner reference"), max_length=128, blank=True,
        help_text=_("This is the item number that the partner uses "
                    "within their system"))
    partner_line_notes = models.TextField(
        _("Partner Notes"), blank=True)

    # We keep a link to the stockrecord used for this line which allows us to
    # update stocklevels when it ships
    stockrecord = models.ForeignKey(
        'partner.StockRecord', on_delete=models.SET_NULL, blank=True,
        null=True, verbose_name=_("Stock record"))

    # PRODUCT INFORMATION
    # -------------------

    # We don't want any hard links between orders and the products table so we
    # allow this link to be NULLable.
    product = models.ForeignKey(
        'catalogue.Product', on_delete=models.SET_NULL, blank=True, null=True,
        verbose_name=_("Product"))
    title = models.CharField(
        pgettext_lazy(u"Product title", u"Title"), max_length=255)
    # UPC can be null because it's usually set as the product's UPC, and that
    # can be null as well
    upc = models.CharField(_("UPC"), max_length=128, blank=True, null=True)

    quantity = models.PositiveIntegerField(_("Quantity"), default=1)

    # REPORTING INFORMATION
    # ---------------------

    # Price information (these fields are actually redundant as the information
    # can be calculated from the LinePrice models
    line_price_incl_tax = models.DecimalField(
        _("Price (inc. tax)"), decimal_places=2, max_digits=12)
    line_price_excl_tax = models.DecimalField(
        _("Price (excl. tax)"), decimal_places=2, max_digits=12)

    # Price information before discounts are applied
    line_price_before_discounts_incl_tax = models.DecimalField(
        _("Price before discounts (inc. tax)"),
        decimal_places=2, max_digits=12)
    line_price_before_discounts_excl_tax = models.DecimalField(
        _("Price before discounts (excl. tax)"),
        decimal_places=2, max_digits=12)

    # Cost price (the price charged by the fulfilment partner for this
    # product).
    unit_cost_price = models.DecimalField(
        _("Unit Cost Price"), decimal_places=2, max_digits=12, blank=True,
        null=True)
    # Normal site price for item (without discounts)
    unit_price_incl_tax = models.DecimalField(
        _("Unit Price (inc. tax)"), decimal_places=2, max_digits=12,
        blank=True, null=True)
    unit_price_excl_tax = models.DecimalField(
        _("Unit Price (excl. tax)"), decimal_places=2, max_digits=12,
        blank=True, null=True)
    # Retail price at time of purchase
    unit_retail_price = models.DecimalField(
        _("Unit Retail Price"), decimal_places=2, max_digits=12,
        blank=True, null=True)

    # Partners often want to assign some status to each line to help with their
    # own business processes.
    status = models.CharField(_("Status"), max_length=255, blank=True)

    # Estimated dispatch date - should be set at order time
    est_dispatch_date = models.DateField(
        _("Estimated Dispatch Date"), blank=True, null=True)

    #: Order status pipeline.  This should be a dict where each (key, value)
    #: corresponds to a status and the possible statuses that can follow that
    #: one.
    pipeline = getattr(settings, 'OSCAR_LINE_STATUS_PIPELINE', {})

    class Meta:
        abstract = True
        app_label = 'order'
        verbose_name = _("Order Line")
        verbose_name_plural = _("Order Lines")

    def __str__(self):
        if self.product:
            title = self.product.title
        else:
            title = _('<missing product>')
        return _("Product '%(name)s', quantity '%(qty)s'") % {
            'name': title, 'qty': self.quantity}

    @classmethod
    def all_statuses(cls):
        """
        Return all possible statuses for an order line
        """
        return list(cls.pipeline.keys())

    def available_statuses(self):
        """
        Return all possible statuses that this order line can move to
        """
        return self.pipeline.get(self.status, ())

    def set_status(self, new_status):
        """
        Set a new status for this line

        If the requested status is not valid, then ``InvalidLineStatus`` is
        raised.
        """
        if new_status == self.status:
            return
        if new_status not in self.available_statuses():
            raise exceptions.InvalidLineStatus(
                _("'%(new_status)s' is not a valid status (current status:"
                  " '%(status)s')")
                % {'new_status': new_status, 'status': self.status})
        self.status = new_status
        self.save()
    set_status.alters_data = True

    @property
    def category(self):
        """
        Used by Google analytics tracking
        """
        return None

    @property
    def description(self):
        """
        Returns a description of this line.
        """
        return self.title

    @property
    def discount_incl_tax(self):
        return self.line_price_before_discounts_incl_tax \
            - self.line_price_incl_tax

    @property
    def discount_excl_tax(self):
        return self.line_price_before_discounts_excl_tax \
            - self.line_price_excl_tax

    @property
    def line_price_tax(self):
        return self.line_price_incl_tax - self.line_price_excl_tax

    @property
    def unit_price_tax(self):
        return self.unit_price_incl_tax - self.unit_price_excl_tax

    # Shipping status helpers

    @property
    def shipping_status(self):
        """
        Returns a string summary of the shipping status of this line
        """
        status_map = self.shipping_event_breakdown
        if not status_map:
            return ''

        events = []
        last_complete_event_name = None
        for event_dict in reversed(list(status_map.values())):
            if event_dict['quantity'] == self.quantity:
                events.append(event_dict['name'])
                last_complete_event_name = event_dict['name']
            else:
                events.append("%s (%d/%d items)" % (
                    event_dict['name'], event_dict['quantity'],
                    self.quantity))

        if last_complete_event_name == list(status_map.values())[0]['name']:
            return last_complete_event_name

        return ', '.join(events)

    def is_shipping_event_permitted(self, event_type, quantity):
        """
        Test whether a shipping event with the given quantity is permitted

        This method should normally be overriden to ensure that the
        prerequisite shipping events have been passed for this line.
        """
        # Note, this calculation is simplistic - normally, you will also need
        # to check if previous shipping events have occurred.  Eg, you can't
        # return lines until they have been shipped.
        current_qty = self.shipping_event_quantity(event_type)
        return (current_qty + quantity) <= self.quantity

    def shipping_event_quantity(self, event_type):
        """
        Return the quantity of this line that has been involved in a shipping
        event of the passed type.
        """
        result = self.shipping_event_quantities.filter(
            event__event_type=event_type).aggregate(Sum('quantity'))
        if result['quantity__sum'] is None:
            return 0
        else:
            return result['quantity__sum']

    def has_shipping_event_occurred(self, event_type, quantity=None):
        """
        Test whether this line has passed a given shipping event
        """
        if not quantity:
            quantity = self.quantity
        return self.shipping_event_quantity(event_type) == quantity

    def get_event_quantity(self, event):
        """
        Fetches the ShippingEventQuantity instance for this line

        Exists as a separate method so it can be overridden to avoid
        the DB query that's caused by get().
        """
        return event.line_quantities.get(line=self)

    @property
    def shipping_event_breakdown(self):
        """
        Returns a dict of shipping events that this line has been through
        """
        status_map = SortedDict()
        for event in self.shipping_events.all():
            event_type = event.event_type
            event_name = event_type.name
            event_quantity = self.get_event_quantity(event).quantity
            if event_name in status_map:
                status_map[event_name]['quantity'] += event_quantity
            else:
                status_map[event_name] = {
                    'event_type': event_type,
                    'name': event_name,
                    'quantity': event_quantity
                }
        return status_map

    # Payment event helpers

    def is_payment_event_permitted(self, event_type, quantity):
        """
        Test whether a payment event with the given quantity is permitted.

        Allow each payment event type to occur only once per quantity.
        """
        current_qty = self.payment_event_quantity(event_type)
        return (current_qty + quantity) <= self.quantity

    def payment_event_quantity(self, event_type):
        """
        Return the quantity of this line that has been involved in a payment
        event of the passed type.
        """
        result = self.payment_event_quantities.filter(
            event__event_type=event_type).aggregate(Sum('quantity'))
        if result['quantity__sum'] is None:
            return 0
        else:
            return result['quantity__sum']

    @property
    def is_product_deleted(self):
        return self.product is None

    def is_available_to_reorder(self, basket, strategy):
        """
        Test if this line can be re-ordered using the passed strategy and
        basket
        """
        if not self.product:
            return False, (_("'%(title)s' is no longer available") %
                           {'title': self.title})

        try:
            basket_line = basket.lines.get(product=self.product)
        except basket.lines.model.DoesNotExist:
            desired_qty = self.quantity
        else:
            desired_qty = basket_line.quantity + self.quantity

        result = strategy.fetch_for_product(self.product)
        is_available, reason = result.availability.is_purchase_permitted(
            quantity=desired_qty)
        if not is_available:
            return False, reason
        return True, None


@python_2_unicode_compatible
class AbstractLinePrice(models.Model):
    """
    For tracking the prices paid for each unit within a line.

    This is necessary as offers can lead to units within a line
    having different prices.  For example, one product may be sold at
    50% off as it's part of an offer while the remainder are full price.
    """
    order = models.ForeignKey(
        'order.Order', related_name='line_prices', verbose_name=_("Option"))
    line = models.ForeignKey(
        'order.Line', related_name='prices', verbose_name=_("Line"))
    quantity = models.PositiveIntegerField(_("Quantity"), default=1)
    price_incl_tax = models.DecimalField(
        _("Price (inc. tax)"), decimal_places=2, max_digits=12)
    price_excl_tax = models.DecimalField(
        _("Price (excl. tax)"), decimal_places=2, max_digits=12)
    shipping_incl_tax = models.DecimalField(
        _("Shiping (inc. tax)"), decimal_places=2, max_digits=12, default=0)
    shipping_excl_tax = models.DecimalField(
        _("Shipping (excl. tax)"), decimal_places=2, max_digits=12, default=0)

    class Meta:
        abstract = True
        app_label = 'order'
        ordering = ('id',)
        verbose_name = _("Line Price")
        verbose_name_plural = _("Line Prices")

    def __str__(self):
        return _("Line '%(number)s' (quantity %(qty)d) price %(price)s") % {
            'number': self.line,
            'qty': self.quantity,
            'price': self.price_incl_tax}


# PAYMENT EVENTS


@python_2_unicode_compatible
class AbstractPaymentEventType(models.Model):
    """
    Payment event types are things like 'Paid', 'Failed', 'Refunded'.

    These are effectively the transaction types.
    """
    name = models.CharField(_("Name"), max_length=128, unique=True)
    code = AutoSlugField(_("Code"), max_length=128, unique=True,
                         populate_from='name')

    class Meta:
        abstract = True
        app_label = 'order'
        verbose_name = _("Payment Event Type")
        verbose_name_plural = _("Payment Event Types")
        ordering = ('name', )

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class AbstractPaymentEvent(models.Model):
    """
    A payment event for an order

    For example:

    * All lines have been paid for
    * 2 lines have been refunded
    """
    order = models.ForeignKey(
        'order.Order', related_name='payment_events',
        verbose_name=_("Order"))
    amount = models.DecimalField(
        _("Amount"), decimal_places=2, max_digits=12)
    # The reference should refer to the transaction ID of the payment gateway
    # that was used for this event.
    reference = models.CharField(
        _("Reference"), max_length=128, blank=True)
    lines = models.ManyToManyField(
        'order.Line', through='PaymentEventQuantity',
        verbose_name=_("Lines"))
    event_type = models.ForeignKey(
        'order.PaymentEventType', verbose_name=_("Event Type"))
    # Allow payment events to be linked to shipping events.  Often a shipping
    # event will trigger a payment event and so we can use this FK to capture
    # the relationship.
    shipping_event = models.ForeignKey(
        'order.ShippingEvent', related_name='payment_events',
        null=True)
    date_created = models.DateTimeField(_("Date created"), auto_now_add=True)

    class Meta:
        abstract = True
        app_label = 'order'
        verbose_name = _("Payment Event")
        verbose_name_plural = _("Payment Events")
        ordering = ['-date_created']

    def __str__(self):
        return _("Payment event for order %s") % self.order

    def num_affected_lines(self):
        return self.lines.all().count()

