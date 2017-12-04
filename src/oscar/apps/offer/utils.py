from contextlib import contextmanager
from itertools import chain
import logging

from django.db.models import Q
from django.utils.timezone import now

from oscar.core.loading import get_model
from oscar.apps.offer import results

ConditionalOffer = get_model('offer', 'ConditionalOffer')

logger = logging.getLogger('oscar.offers')





class Applicator(object):

    def apply(self, basket, user=None, request=None):
        """
        Apply all relevant offers to the given basket.

        The request is passed too as sometimes the available offers
        are dependent on the user (eg session-based offers).
        """
        offers = self.get_offers(basket, user, request)
        self.apply_offers_to_basket(basket, offers)

    def apply_offers_to_basket(self, basket, offers):
        set_of_lines = SetOfLines.from_basket(basket)

        applications = self.apply_offers(set_of_lines, offers, basket.owner)
        basket_lines_by_ref = {line.line_reference: line
                               for line in basket.all_lines()}
        for line in set_of_lines:
            basket_lines_by_ref[line.reference].discount(
                line.get_discount_value(), line.quantity_with_benefits(),
                incl_tax=True)
        # Store this list of discounts with the basket so it can be
        # rendered in templates
        basket.offer_applications = applications

    def apply_offers(self, set_of_lines, offers, user=None):
        applications = results.OfferApplications()
        for offer in offers:
            num_applications = 0
            # Keep applying the offer until either
            # (a) We reach the max number of applications for the offer.
            # (b) The benefit can't be applied successfully.
            while num_applications < offer.get_max_applications(user):
                result = offer.apply_benefit(set_of_lines)
                num_applications += 1
                if not result.is_successful:
                    break
                applications.add(offer, result)
                if result.is_final:
                    break

        return applications

    def get_offers(self, basket, user=None, request=None):
        """
        Return all offers to apply to the basket.

        This method should be subclassed and extended to provide more
        sophisticated behaviour.  For instance, you could load extra offers
        based on the session or the user type.
        """
        self._request = request

        site_offers = self.get_site_offers()
        basket_offers = self.get_basket_offers(basket, user)
        user_offers = self.get_user_offers(user)
        session_offers = self.get_session_offers(request)

        return list(sorted(chain(
            session_offers, basket_offers, user_offers, site_offers),
            key=lambda o: o.priority, reverse=True))

    def _get_available_offers(self):
        cutoff = now()
        date_based = Q(
            Q(start_datetime__lte=cutoff),
            Q(end_datetime__gte=cutoff) | Q(end_datetime=None),
        )

        nondate_based = Q(start_datetime=None, end_datetime=None)

        qs = ConditionalOffer.objects.filter(
            date_based | nondate_based,
            status=ConditionalOffer.OPEN)
        # Using select_related with the condition/benefit ranges doesn't
        # seem to work.  I think this is because both the related objects
        # have the FK to range with the same name.
        return qs.select_related('condition', 'benefit', 'benefit__range')

    def get_available_offers(self):
        if self._request is None:
            return self._get_available_offers()

        if not hasattr(self._request, '_available_offers'):
            self._request._available_offers = self._get_available_offers()

        return self._request._available_offers

    def get_site_offers(self):
        """
        Return site offers that are available to all users
        """
        return [offer for offer in self.get_available_offers()
                if offer.offer_type == ConditionalOffer.SITE]

    def get_basket_offers(self, basket, user):
        """
        Return basket-linked offers such as those associated with a voucher
        code
        """
        offers = []
        if not basket.id or not user:
            return offers

        for voucher in basket.vouchers.all():
            is_available_to_user, _ = voucher.is_available_to_user(user)
            if voucher.is_active() and is_available_to_user:
                basket_offers = voucher.offers.all()
                for offer in basket_offers:
                    offer.set_voucher(voucher)
                offers = list(chain(offers, basket_offers))
        return offers

    def get_user_offers(self, user):
        """
        Returns offers linked to this particular user.

        Eg: student users might get 25% off
        """
        return []

    def get_session_offers(self, request):
        """
        Returns temporary offers linked to the current session.

        Eg: visitors coming from an affiliate site get a 10% discount
        """
        return []
