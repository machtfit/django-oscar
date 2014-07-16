import six
from decimal import Decimal as D, ROUND_DOWN

from django.core import exceptions
from django.template.defaultfilters import date as date_filter
from django.db import models
from django.utils.timezone import now, get_current_timezone
from django.utils.translation import ungettext, ugettext_lazy as _
from django.utils.importlib import import_module
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.conf import settings

from oscar.core.utils import slugify
from oscar.core.loading import get_class, get_model
from oscar.apps.offer.managers import ActiveOfferManager
from oscar.templatetags.currency_filters import currency
from oscar.models import fields

BrowsableRangeManager = get_class('offer.managers', 'BrowsableRangeManager')


def load_proxy(proxy_class):
    module, classname = proxy_class.rsplit('.', 1)
    try:
        mod = import_module(module)
    except ImportError as e:
        raise exceptions.ImproperlyConfigured(
            "Error importing module %s: %s" % (module, e))
    try:
        return getattr(mod, classname)
    except AttributeError:
        raise exceptions.ImproperlyConfigured(
            "Module %s does not define a %s" % (module, classname))


def range_anchor(range):
    return u'<a href="%s">%s</a>' % (
        reverse('dashboard:range-update', kwargs={'pk': range.pk}),
        range.name)


class ConditionalOffer(models.Model):
    """
    A conditional offer (eg buy 1, get 10% off)
    """
    name = models.CharField(
        _("Name"), max_length=128, unique=True,
        help_text=_("This is displayed within the customer's basket"))
    slug = fields.AutoSlugField(
        _("Slug"), max_length=128, unique=True, populate_from='name')
    description = models.TextField(_("Description"), blank=True,
                                   help_text=_("This is displayed on the offer"
                                               " browsing page"))

    # Offers come in a few different types:
    # (a) Offers that are available to all customers on the site.  Eg a
    #     3-for-2 offer.
    # (b) Offers that are linked to a voucher, and only become available once
    #     that voucher has been applied to the basket
    # (c) Offers that are linked to a user.  Eg, all students get 10% off.  The
    #     code to apply this offer needs to be coded
    # (d) Session offers - these are temporarily available to a user after some
    #     trigger event.  Eg, users coming from some affiliate site get 10%
    #     off.
    SITE, VOUCHER, USER, SESSION = ("Site", "Voucher", "User", "Session")
    TYPE_CHOICES = (
        (SITE, _("Site offer - available to all users")),
        (VOUCHER, _("Voucher offer - only available after entering "
                    "the appropriate voucher code")),
        (USER, _("User offer - available to certain types of user")),
        (SESSION, _("Session offer - temporary offer, available for "
                    "a user for the duration of their session")),
    )
    offer_type = models.CharField(
        _("Type"), choices=TYPE_CHOICES, default=SITE, max_length=128)

    # We track a status variable so it's easier to load offers that are
    # 'available' in some sense.
    OPEN, SUSPENDED, CONSUMED = "Open", "Suspended", "Consumed"
    status = models.CharField(_("Status"), max_length=64, default=OPEN)

    condition = models.ForeignKey(
        'offer.Condition', verbose_name=_("Condition"))
    benefit = models.ForeignKey('offer.Benefit', verbose_name=_("Benefit"))

    # Some complicated situations require offers to be applied in a set order.
    priority = models.IntegerField(
        _("Priority"), default=0,
        help_text=_("The highest priority offers are applied first"))

    # AVAILABILITY

    # Range of availability.  Note that if this is a voucher offer, then these
    # dates are ignored and only the dates from the voucher are used to
    # determine availability.
    start_datetime = models.DateTimeField(
        _("Start date"), blank=True, null=True)
    end_datetime = models.DateTimeField(
        _("End date"), blank=True, null=True,
        help_text=_("Offers are active until the end of the 'end date'"))

    # Use this field to limit the number of times this offer can be applied in
    # total.  Note that a single order can apply an offer multiple times so
    # this is not the same as the number of orders that can use it.
    max_global_applications = models.PositiveIntegerField(
        _("Max global applications"),
        help_text=_("The number of times this offer can be used before it "
                    "is unavailable"), blank=True, null=True)

    # Use this field to limit the number of times this offer can be used by a
    # single user.  This only works for signed-in users - it doesn't really
    # make sense for sites that allow anonymous checkout.
    max_user_applications = models.PositiveIntegerField(
        _("Max user applications"),
        help_text=_("The number of times a single user can use this offer"),
        blank=True, null=True)

    # Use this field to limit the number of times this offer can be applied to
    # a basket (and hence a single order).
    max_basket_applications = models.PositiveIntegerField(
        _("Max basket applications"),
        blank=True, null=True,
        help_text=_("The number of times this offer can be applied to a "
                    "basket (and order)"))

    # Use this field to limit the amount of discount an offer can lead to.
    # This can be helpful with budgeting.
    max_discount = models.DecimalField(
        _("Max discount"), decimal_places=2, max_digits=12, null=True,
        blank=True,
        help_text=_("When an offer has given more discount to orders "
                    "than this threshold, then the offer becomes "
                    "unavailable"))

    # TRACKING

    total_discount = models.DecimalField(
        _("Total Discount"), decimal_places=2, max_digits=12,
        default=D('0.00'))
    num_applications = models.PositiveIntegerField(
        _("Number of applications"), default=0)
    num_orders = models.PositiveIntegerField(
        _("Number of Orders"), default=0)

    redirect_url = fields.ExtendedURLField(
        _("URL redirect (optional)"), blank=True)
    date_created = models.DateTimeField(_("Date Created"), auto_now_add=True)

    objects = models.Manager()
    active = ActiveOfferManager()

    # We need to track the voucher that this offer came from (if it is a
    # voucher offer)
    _voucher = None

    class Meta:
        ordering = ['-priority']
        verbose_name = _("Conditional offer")
        verbose_name_plural = _("Conditional offers")

    def save(self, *args, **kwargs):
        # Check to see if consumption thresholds have been broken
        if not self.is_suspended:
            if self.get_max_applications() == 0:
                self.status = self.CONSUMED
            else:
                self.status = self.OPEN

        return super(ConditionalOffer, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('offer:detail', kwargs={'slug': self.slug})

    def __unicode__(self):
        return self.name

    def clean(self):
        if (self.start_datetime and self.end_datetime and
                self.start_datetime > self.end_datetime):
            raise exceptions.ValidationError(
                _('End date should be later than start date'))

    @property
    def is_open(self):
        return self.status == self.OPEN

    @property
    def is_suspended(self):
        return self.status == self.SUSPENDED

    def suspend(self):
        self.status = self.SUSPENDED
        self.save()
    suspend.alters_data = True

    def unsuspend(self):
        self.status = self.OPEN
        self.save()
    suspend.alters_data = True

    def is_available(self, user=None, test_date=None):
        """
        Test whether this offer is available to be used
        """
        if self.is_suspended:
            return False
        if test_date is None:
            test_date = now()
        predicates = []
        if self.start_datetime:
            predicates.append(self.start_datetime > test_date)
        if self.end_datetime:
            predicates.append(test_date > self.end_datetime)
        if any(predicates):
            return False
        return self.get_max_applications(user) > 0

    def is_condition_partially_satisfied(self, basket):
        return self.condition.proxy().is_partially_satisfied(self, basket)

    def get_upsell_message(self, basket):
        return self.condition.proxy().get_upsell_message(self, basket)

    def apply_benefit(self, set_of_lines):
        """
        Applies the benefit to the given set of lines and returns the discount.
        """
        condition = self.condition.proxy()
        benefit = self.benefit.proxy()

        with set_of_lines.begin_transaction() as transaction:
            if not condition.is_satisfied(set_of_lines):
                transaction.rollback()
                return ZERO_DISCOUNT

            result = benefit.apply(set_of_lines)

            if not result:
                transaction.rollback()
                return ZERO_DISCOUNT

        return result

    def apply_deferred_benefit(self, basket, order, application):
        """
        Applies any deferred benefits.  These are things like adding loyalty
        points to somone's account.
        """
        return self.benefit.proxy().apply_deferred(basket, order, application)

    def set_voucher(self, voucher):
        self._voucher = voucher

    def get_voucher(self):
        return self._voucher

    def get_max_applications(self, user=None):
        """
        Return the number of times this offer can be applied to a basket for a
        given user.
        """
        if self.max_discount and self.total_discount >= self.max_discount:
            return 0

        # Hard-code a maximum value as we need some sensible upper limit for
        # when there are not other caps.
        limits = [10000]
        if self.max_user_applications and user:
            limits.append(max(0, self.max_user_applications -
                          self.get_num_user_applications(user)))
        if self.max_basket_applications:
            limits.append(self.max_basket_applications)
        if self.max_global_applications:
            limits.append(
                max(0, self.max_global_applications - self.num_applications))
        return min(limits)

    def get_num_user_applications(self, user):
        OrderDiscount = models.get_model('order', 'OrderDiscount')
        aggregates = OrderDiscount.objects.filter(offer_id=self.id,
                                                  order__user=user)\
            .aggregate(total=models.Sum('frequency'))
        return aggregates['total'] if aggregates['total'] is not None else 0

    def shipping_discount(self, charge):
        return self.benefit.proxy().shipping_discount(charge)

    def record_usage(self, discount):
        self.num_applications += discount['freq']
        self.total_discount += discount['discount']
        self.num_orders += 1
        self.save()
    record_usage.alters_data = True

    def availability_description(self):
        """
        Return a description of when this offer is available
        """
        restrictions = self.availability_restrictions()
        descriptions = [r['description'] for r in restrictions]
        return "<br/>".join(descriptions)

    def availability_restrictions(self):  # noqa (too complex (15))
        restrictions = []
        if self.is_suspended:
            restrictions.append({
                'description': _("Offer is suspended"),
                'is_satisfied': False})

        if self.max_global_applications:
            remaining = self.max_global_applications - self.num_applications
            desc = _("Limited to %(total)d uses (%(remainder)d remaining)") \
                % {'total': self.max_global_applications,
                   'remainder': remaining}
            restrictions.append({'description': desc,
                                 'is_satisfied': remaining > 0})

        if self.max_user_applications:
            if self.max_user_applications == 1:
                desc = _("Limited to 1 use per user")
            else:
                desc = _("Limited to %(total)d uses per user") \
                    % {'total': self.max_user_applications}
            restrictions.append({'description': desc,
                                 'is_satisfied': True})

        if self.max_basket_applications:
            if self.max_user_applications == 1:
                desc = _("Limited to 1 use per basket")
            else:
                desc = _("Limited to %(total)d uses per basket") \
                    % {'total': self.max_basket_applications}
            restrictions.append({
                'description': desc,
                'is_satisfied': True})

        def hide_time_if_zero(dt):
            # Only show hours/minutes if they have been specified
            if dt.tzinfo:
                localtime = dt.astimezone(get_current_timezone())
            else:
                localtime = dt
            if localtime.hour == 0 and localtime.minute == 0:
                return date_filter(localtime, settings.DATE_FORMAT)
            return date_filter(localtime, settings.DATETIME_FORMAT)

        if self.start_datetime or self.end_datetime:
            today = now()
            if self.start_datetime and self.end_datetime:
                desc = _("Available between %(start)s and %(end)s") \
                    % {'start': hide_time_if_zero(self.start_datetime),
                       'end': hide_time_if_zero(self.end_datetime)}
                is_satisfied \
                    = self.start_datetime <= today <= self.end_datetime
            elif self.start_datetime:
                desc = _("Available from %(start)s") % {
                    'start': hide_time_if_zero(self.start_datetime)}
                is_satisfied = today >= self.start_datetime
            elif self.end_datetime:
                desc = _("Available until %(end)s") % {
                    'end': hide_time_if_zero(self.end_datetime)}
                is_satisfied = today <= self.end_datetime
            restrictions.append({
                'description': desc,
                'is_satisfied': is_satisfied})

        if self.max_discount:
            desc = _("Limited to a cost of %(max)s") % {
                'max': currency(self.max_discount)}
            restrictions.append({
                'description': desc,
                'is_satisfied': self.total_discount < self.max_discount})

        return restrictions

    @property
    def has_products(self):
        return self.condition.range is not None

    def products(self):
        """
        Return a queryset of products in this offer
        """
        Product = get_model('catalogue', 'Product')
        if not self.has_products:
            return Product.objects.none()

        cond_range = self.condition.range
        if cond_range.includes_all_products:
            # Return ALL the products
            return Product.browsable.select_related('product_class',
                                                    'stockrecord')\
                .filter(is_discountable=True)\
                .prefetch_related('children', 'images',
                                  'product_class__options', 'product_options')
        return cond_range.included_products.filter(is_discountable=True)


class Condition(models.Model):
    NONE = "None"
    TYPE_CHOICES = (
        (NONE, _("Place no restriction on the basket")),)
    range = models.ForeignKey(
        'offer.Range', verbose_name=_("Range"), null=True, blank=True)
    type = models.CharField(_('Type'), max_length=128, choices=TYPE_CHOICES,
                            blank=True)
    value = fields.PositiveDecimalField(
        _('Value'), decimal_places=2, max_digits=12, null=True, blank=True)

    proxy_class = fields.NullCharField(
        _("Custom class"), max_length=255, unique=True, default=None)

    class Meta:
        verbose_name = _("Condition")
        verbose_name_plural = _("Conditions")

    def proxy(self):
        """
        Return the proxy model
        """
        field_dict = dict(self.__dict__)
        for field in list(field_dict.keys()):
            if field.startswith('_'):
                del field_dict[field]

        if self.proxy_class:
            klass = load_proxy(self.proxy_class)
            return klass(**field_dict)
        klassmap = {
            self.NONE: NoneCondition}
        if self.type in klassmap:
            return klassmap[self.type](**field_dict)
        return self

    def __unicode__(self):
        return self.proxy().name

    @property
    def name(self):
        """
        A plaintext description of the condition.

        This is used in the dropdowns within the offer dashboard.
        """
        return self.description

    @property
    def description(self):
        """
        A (optionally HTML) description of the condition.
        """
        return self.proxy().description

    def is_satisfied(self, set_of_lines):
        """
        Determine whether a given set of lines meets this condition.  Mark the
        quantity of items that are needed to meet this condition.

        This is stubbed in this top-class object.  The subclassing proxies are
        responsible for implementing it correctly.
        """
        return False

    def is_partially_satisfied(self, offer, basket):
        """
        Determine if the basket partially meets the condition.  This is useful
        for up-selling messages to entice customers to buy something more in
        order to qualify for an offer.
        """
        return False

    def get_upsell_message(self, offer, basket):
        return None


class Benefit(models.Model):
    range = models.ForeignKey(
        'offer.Range', null=True, blank=True, verbose_name=_("Range"))

    # Benefit types
    PERCENTAGE = "Percentage"
    SHIPPING_PERCENTAGE, SHIPPING_ABSOLUTE, SHIPPING_FIXED_PRICE = (
        'Shipping percentage', 'Shipping absolute', 'Shipping fixed price')
    TYPE_CHOICES = (
        (PERCENTAGE, _("Discount is a percentage off of the product's value")),
        (SHIPPING_ABSOLUTE,
         _("Discount is a fixed amount of the shipping cost")),
        (SHIPPING_FIXED_PRICE, _("Get shipping for a fixed price")),
        (SHIPPING_PERCENTAGE, _("Discount is a percentage off of the shipping"
                                " cost")),
    )
    type = models.CharField(
        _("Type"), max_length=128, choices=TYPE_CHOICES, blank=True)

    # The value to use with the designated type.  This can be either an integer
    # (eg for multibuy) or a decimal (eg an amount) which is slightly
    # confusing.
    value = fields.PositiveDecimalField(
        _("Value"), decimal_places=2, max_digits=12, null=True, blank=True)

    # If this is not set, then there is no upper limit on how many products
    # can be discounted by this benefit.
    max_affected_items = models.PositiveIntegerField(
        _("Max Affected Items"), blank=True, null=True,
        help_text=_("Set this to prevent the discount consuming all items "
                    "within the range that are in the basket."))

    # A custom benefit class can be used instead.  This means the
    # type/value/max_affected_items fields should all be None.
    proxy_class = fields.NullCharField(
        _("Custom class"), max_length=255, unique=True, default=None)

    class Meta:
        verbose_name = _("Benefit")
        verbose_name_plural = _("Benefits")

    def proxy(self):
        klassmap = {
            self.PERCENTAGE: PercentageDiscountBenefit,
            self.SHIPPING_ABSOLUTE: ShippingAbsoluteDiscountBenefit,
            self.SHIPPING_FIXED_PRICE: ShippingFixedPriceBenefit,
            self.SHIPPING_PERCENTAGE: ShippingPercentageDiscountBenefit}

        if self.__class__ in klassmap.values():
            return self

        field_dict = dict(self.__dict__)
        for field in list(field_dict.keys()):
            if field.startswith('_'):
                del field_dict[field]

        if self.proxy_class:
            klass = load_proxy(self.proxy_class)
            if self.__class__ == klass:
                return self
            return klass(**field_dict)

        if self.type in klassmap:
            return klassmap[self.type](**field_dict)
        raise RuntimeError("Unrecognised benefit type (%s)" % self.type)

    def __unicode__(self):
        name = self.proxy().name
        if self.max_affected_items:
            name += ungettext(
                " (max %d item)",
                " (max %d items)",
                self.max_affected_items) % self.max_affected_items
        return name

    @property
    def name(self):
        return self.description

    @property
    def description(self):
        return self.proxy().description

    def apply(self, set_of_lines):
        """
        Apply a discount to lines.

        Return `False` if no discount could be applied. This frees up the lines
        used in the condition for other offers.
        """
        return False

    def apply_deferred(self, basket, order, application):
        return None

    def clean(self):
        if not self.type:
            return
        method_name = 'clean_%s' % self.type.lower().replace(' ', '_')
        if hasattr(self, method_name):
            getattr(self, method_name)()

    def clean_multibuy(self):
        if not self.range:
            raise ValidationError(
                _("Multibuy benefits require a product range"))
        if self.value:
            raise ValidationError(
                _("Multibuy benefits don't require a value"))
        if self.max_affected_items:
            raise ValidationError(
                _("Multibuy benefits don't require a 'max affected items' "
                  "attribute"))

    def clean_percentage(self):
        if not self.range:
            raise ValidationError(
                _("Percentage benefits require a product range"))
        if self.value > 100:
            raise ValidationError(
                _("Percentage discount cannot be greater than 100"))

    def clean_shipping_absolute(self):
        if not self.value:
            raise ValidationError(
                _("A discount value is required"))
        if self.range:
            raise ValidationError(
                _("No range should be selected as this benefit does not "
                  "apply to products"))
        if self.max_affected_items:
            raise ValidationError(
                _("Shipping discounts don't require a 'max affected items' "
                  "attribute"))

    def clean_shipping_percentage(self):
        if self.value > 100:
            raise ValidationError(
                _("Percentage discount cannot be greater than 100"))
        if self.range:
            raise ValidationError(
                _("No range should be selected as this benefit does not "
                  "apply to products"))
        if self.max_affected_items:
            raise ValidationError(
                _("Shipping discounts don't require a 'max affected items' "
                  "attribute"))

    def clean_shipping_fixed_price(self):
        if self.range:
            raise ValidationError(
                _("No range should be selected as this benefit does not "
                  "apply to products"))
        if self.max_affected_items:
            raise ValidationError(
                _("Shipping discounts don't require a 'max affected items' "
                  "attribute"))

    def clean_fixed_price(self):
        if self.range:
            raise ValidationError(
                _("No range should be selected as the condition range will "
                  "be used instead."))

    def clean_absolute(self):
        if not self.range:
            raise ValidationError(
                _("Fixed discount benefits require a product range"))
        if not self.value:
            raise ValidationError(
                _("Fixed discount benefits require a value"))

    def round(self, amount):
        """
        Apply rounding to discount amount
        """
        if hasattr(settings, 'OSCAR_OFFER_ROUNDING_FUNCTION'):
            return settings.OSCAR_OFFER_ROUNDING_FUNCTION(amount)
        return amount.quantize(D('.01'), ROUND_DOWN)

    def _effective_max_affected_items(self):
        """
        Return the maximum number of items that can have a discount applied
        during the application of this benefit
        """
        return self.max_affected_items if self.max_affected_items else 10000

    def filter_lines(self, set_of_lines):
        """
        Return only those lines that can be used for this benefit.
        """
        # We sort lines to be cheapest first to ensure consistent applications
        return sorted([line for line
                       in set_of_lines.get_lines_available_for_benefit()
                       if self.range.contains_product(line.product)],
                      key=lambda line: line.price)

    def shipping_discount(self, charge):
        return D('0.00')


class Range(models.Model):
    """
    Represents a range of products that can be used within an offer
    """
    name = models.CharField(_("Name"), max_length=128, unique=True)
    slug = models.SlugField(_('Slug'), max_length=128, unique=True, null=True)

    description = models.TextField(blank=True)

    # Whether this range is public
    is_public = models.BooleanField(
        _('Is public?'), default=False,
        help_text=_("Public ranges have a customer-facing page"))

    includes_all_products = models.BooleanField(
        _('Includes all products?'), default=False)

    included_products = models.ManyToManyField(
        'catalogue.Product', related_name='includes', blank=True,
        verbose_name=_("Included Products"), through='offer.RangeProduct')
    excluded_products = models.ManyToManyField(
        'catalogue.Product', related_name='excludes', blank=True,
        verbose_name=_("Excluded Products"))
    classes = models.ManyToManyField(
        'catalogue.ProductClass', related_name='classes', blank=True,
        verbose_name=_("Product Types"))
    included_categories = models.ManyToManyField(
        'catalogue.Category', related_name='includes', blank=True,
        verbose_name=_("Included Categories"))

    # Allow a custom range instance to be specified
    proxy_class = fields.NullCharField(
        _("Custom class"), max_length=255, default=None, unique=True)

    date_created = models.DateTimeField(_("Date Created"), auto_now_add=True)

    __included_product_ids = None
    __excluded_product_ids = None
    __class_ids = None

    objects = models.Manager()
    browsable = BrowsableRangeManager()

    class Meta:
        verbose_name = _("Range")
        verbose_name_plural = _("Ranges")

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('catalogue:range', kwargs={
            'slug': self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        # Save Range
        super(Range, self).save(*args, **kwargs)

    def add_product(self, product, display_order=None):
        """ Add product to the range

        When adding product that is already in the range, prevent re-adding it.
        If display_order is specified, update it.

        Standard display_order for a new product in the range (0) puts
        the product at the top of the list.

        display_order needs to be tested for None because

          >>> display_order = 0
          >>> not display_order
          True
          >>> display_order is None
          False
        """
        initial_order = 0 if display_order is None else display_order
        relation, __ = RangeProduct.objects.get_or_create(
            range=self, product=product,
            defaults={'display_order': initial_order})

        if (display_order is not None and
                relation.display_order != display_order):
            relation.display_order = display_order
            relation.save()

    def remove_product(self, product):
        """ Remove product from range """
        RangeProduct.objects.filter(range=self, product=product).delete()

    def contains_product(self, product):  # noqa (too complex (12))
        """
        Check whether the passed product is part of this range
        """
        # We look for shortcircuit checks first before
        # the tests that require more database queries.

        if settings.OSCAR_OFFER_BLACKLIST_PRODUCT and \
                settings.OSCAR_OFFER_BLACKLIST_PRODUCT(product):
            return False

        # Delegate to a proxy class if one is provided
        if self.proxy_class:
            return load_proxy(self.proxy_class)().contains_product(product)

        excluded_product_ids = self._excluded_product_ids()
        if product.id in excluded_product_ids:
            return False
        if self.includes_all_products:
            return True
        if product.product_class_id in self._class_ids():
            return True
        included_product_ids = self._included_product_ids()
        if product.id in included_product_ids:
            return True
        test_categories = self.included_categories.all()
        if test_categories:
            for category in product.categories.all():
                for test_category in test_categories:
                    if category == test_category \
                            or category.is_descendant_of(test_category):
                        return True
        return False

    # Shorter alias
    contains = contains_product

    def _included_product_ids(self):
        if self.__included_product_ids is None:
            self.__included_product_ids = [row['id'] for row in
                                           self.included_products.values('id')]
        return self.__included_product_ids

    def _excluded_product_ids(self):
        if not self.id:
            return []
        if self.__excluded_product_ids is None:
            self.__excluded_product_ids = [row['id'] for row in
                                           self.excluded_products.values('id')]
        return self.__excluded_product_ids

    def _class_ids(self):
        if None == self.__class_ids:
            self.__class_ids = [row['id'] for row in self.classes.values('id')]
        return self.__class_ids

    def num_products(self):
        # Delegate to a proxy class if one is provided
        if self.proxy_class:
            return load_proxy(self.proxy_class)().num_products()
        if self.includes_all_products:
            return None
        return self.included_products.all().count()

    @property
    def is_editable(self):
        """
        Test whether this product can be edited in the dashboard
        """
        return not self.proxy_class


class RangeProduct(models.Model):
    """ Allow ordering products inside ranges """
    range = models.ForeignKey('offer.Range')
    product = models.ForeignKey('catalogue.Product')
    display_order = models.IntegerField(default=0)

    class Meta:
        unique_together = ('range', 'product')

# ==========
# Conditions
# ==========


class NoneCondition(Condition):
    """
    An offer condition that's always satisfied.
    """
    _description = _("TODO. Count: %(count)d range: %(range)s")

    @property
    def name(self):
        return self._description % {
            'count': self.value,
            'range': six.text_type(self.range).lower()}

    @property
    def description(self):
        return self._description % {
            'count': self.value,
            'range': range_anchor(self.range)}

    class Meta:
        proxy = True
        verbose_name = _("No Condition")
        verbose_name_plural = _("No Conditions")

    def is_satisfied(self, set_of_lines):
        """
        Determines whether a given set of lines meets this condition
        """
        return True

    def is_partially_satisfied(self, offer, basket):
        return False


# ============
# Result types
# ============


class ApplicationResult(object):
    is_final = is_successful = False
    # Basket discount
    discount = D('0.00')
    description = None

    # Offer applications can affect 3 distinct things
    # (a) Give a discount off the BASKET total
    # (b) Give a discount off the SHIPPING total
    # (a) Trigger a post-order action
    BASKET, SHIPPING, POST_ORDER = list(range(0, 3))
    affects = None

    @property
    def affects_basket(self):
        return self.affects == self.BASKET

    @property
    def affects_shipping(self):
        return self.affects == self.SHIPPING

    @property
    def affects_post_order(self):
        return self.affects == self.POST_ORDER


class BasketDiscount(ApplicationResult):
    """
    For when an offer application leads to a simple discount off the basket's
    total
    """
    affects = ApplicationResult.BASKET

    def __init__(self, amount):
        self.discount = amount

    @property
    def is_successful(self):
        return self.discount > 0

    def __str__(self):
        return '<Basket discount of %s>' % self.discount

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.discount)


# Helper global as returning zero discount is quite common
ZERO_DISCOUNT = BasketDiscount(D('0.00'))


class ShippingDiscount(ApplicationResult):
    """
    For when an offer application leads to a discount from the shipping cost
    """
    is_successful = is_final = True
    affects = ApplicationResult.SHIPPING


SHIPPING_DISCOUNT = ShippingDiscount()


class PostOrderAction(ApplicationResult):
    """
    For when an offer condition is met but the benefit is deferred until after
    the order has been placed.  Eg buy 2 books and get 100 loyalty points.
    """
    is_final = is_successful = True
    affects = ApplicationResult.POST_ORDER

    def __init__(self, description):
        self.description = description


# ========
# Benefits
# ========


class PercentageDiscountBenefit(Benefit):
    """
    An offer benefit that gives a percentage discount
    """
    _description = _("%(value)s%% discount on %(range)s")

    @property
    def name(self):
        return self._description % {
            'value': self.value,
            'range': self.range.name}

    @property
    def description(self):
        return self._description % {
            'value': self.value,
            'range': range_anchor(self.range)}

    class Meta:
        proxy = True
        verbose_name = _("Percentage discount benefit")
        verbose_name_plural = _("Percentage discount benefits")

    def apply(self, set_of_lines, discount_percent=None,
              max_total_discount=None):
        """
        Apply a discount of `discount_percent` (defaults to `self.value`)
        percent to all items in the range, but limiting
            * the maximum total discount to `max_total_discount`
            * the maximum number of items discounted to
              `self.max_affected_items`
        """
        if discount_percent is None:
            discount_percent = self.value

        discount_amount_available = max_total_discount

        discount = 0
        affected_quantity_allowed = self._effective_max_affected_items()

        for line in self.filter_lines(set_of_lines):
            if affected_quantity_allowed == 0:
                break

            if discount_amount_available == 0:
                break

            affected_quantity = min(line.quantity_available_for_benefit(),
                                    affected_quantity_allowed)

            line_discount = self.round(discount_percent / D('100.0')
                                       * line.price
                                       * affected_quantity)

            if discount_amount_available is not None:
                line_discount = min(line_discount, discount_amount_available)
                discount_amount_available -= line_discount

            set_of_lines.mark_for_benefit(line, self, affected_quantity,
                                          line_discount)

            affected_quantity_allowed -= affected_quantity
            discount += line_discount

        if discount == 0:
            return False

        return BasketDiscount(discount)


# =================
# Shipping benefits
# =================


class ShippingBenefit(Benefit):

    def apply(self, set_of_lines):
        return SHIPPING_DISCOUNT

    class Meta:
        proxy = True


class ShippingAbsoluteDiscountBenefit(ShippingBenefit):
    _description = _("%(amount)s off shipping cost")

    @property
    def description(self):
        return self._description % {
            'amount': currency(self.value)}

    class Meta:
        proxy = True
        verbose_name = _("Shipping absolute discount benefit")
        verbose_name_plural = _("Shipping absolute discount benefits")

    def shipping_discount(self, charge):
        return min(charge, self.value)


class ShippingFixedPriceBenefit(ShippingBenefit):
    _description = _("Get shipping for %(amount)s")

    @property
    def description(self):
        return self._description % {
            'amount': currency(self.value)}

    class Meta:
        proxy = True
        verbose_name = _("Fixed price shipping benefit")
        verbose_name_plural = _("Fixed price shipping benefits")

    def shipping_discount(self, charge):
        if charge < self.value:
            return D('0.00')
        return charge - self.value


class ShippingPercentageDiscountBenefit(ShippingBenefit):
    _description = _("%(value)s%% off of shipping cost")

    @property
    def description(self):
        return self._description % {
            'value': self.value}

    class Meta:
        proxy = True
        verbose_name = _("Shipping percentage discount benefit")
        verbose_name_plural = _("Shipping percentage discount benefits")

    def shipping_discount(self, charge):
        discount = charge * self.value / D('100.0')
        return discount.quantize(D('0.01'))
