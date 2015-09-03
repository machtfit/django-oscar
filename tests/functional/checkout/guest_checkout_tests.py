import sys

from django.test.utils import override_settings
from django.core.urlresolvers import reverse
from django.conf import settings
from django.utils.http import urlquote
import mock
from six.moves.urllib.parse import urlsplit

from oscar.core.compat import get_user_model
from oscar.core.loading import get_class, get_classes, get_model
from oscar.apps.shipping import methods
from oscar.test.testcases import WebTestCase
from oscar.test import factories
from . import CheckoutMixin

GatewayForm = get_class('checkout.forms', 'GatewayForm')
RedirectRequired, UnableToTakePayment, PaymentError = get_classes(
    'payment.exceptions', [
        'RedirectRequired', 'UnableToTakePayment', 'PaymentError'])
UnableToPlaceOrder = get_class('order.exceptions', 'UnableToPlaceOrder')

Basket = get_model('basket', 'Basket')
User = get_user_model()

# Python 3 compat
try:
    from imp import reload
except ImportError:
    pass

try:
    from importlib import import_module
except ImportError:
    from django.utils.importlib import import_module


def reload_url_conf():
    # Reload URLs to pick up the overridden settings
    if settings.ROOT_URLCONF in sys.modules:
        reload(sys.modules[settings.ROOT_URLCONF])
    import_module(settings.ROOT_URLCONF)


@override_settings(OSCAR_ALLOW_ANON_CHECKOUT=True)
class TestIndexView(CheckoutMixin, WebTestCase):
    is_anonymous = True

    def setUp(self):
        reload_url_conf()
        super(TestIndexView, self).setUp()

    def test_redirects_customers_with_empty_basket(self):
        response = self.get(reverse('checkout:index'))
        self.assertRedirectsTo(response, 'basket:summary')

    def test_redirects_customers_with_invalid_basket(self):
        # Add product to basket but then remove its stock so it is not
        # purchasable.
        product = factories.ProductFactory()
        self.add_product_to_basket(product)
        product.stockrecords.all().update(num_in_stock=0)

        response = self.get(reverse('checkout:index'))
        self.assertRedirectsTo(response, 'basket:summary')

    def test_redirects_customers_who_have_not_identified(self):
        self.add_product_to_basket()
        response = self.get(reverse('checkout:index'))
        self.assertRedirectsTo(response, 'checkout:identify-user')

    def test_redirects_customers_whose_basket_doesnt_require_shipping(self):
        product = self.create_digital_product()
        self.add_product_to_basket(product)
        self.enter_guest_details()

        response = self.get(reverse('checkout:index'))
        self.assertRedirectsTo(response, 'checkout:preview')

    def test_redirects_customers_to_shipping_address_form(self):
        self.add_product_to_basket()
        self.enter_guest_details()

        response = self.get(reverse('checkout:index'))
        self.assertRedirectsTo(response, 'checkout:shipping-address')

    @mock.patch('oscar.apps.checkout.session.Repository')
    def test_redirects_customers_to_shipping_method_step(self, mock_repo):
        self.add_product_to_basket()
        self.enter_guest_details()
        self.enter_shipping_address()

        # Ensure multiple shipping methods available
        method = mock.MagicMock()
        method.code = 'm'
        instance = mock_repo.return_value
        instance.get_shipping_methods.return_value = [methods.Free(), method]

        response = self.get(reverse('checkout:index'))
        self.assertRedirectsTo(response, 'checkout:shipping-method')

    @mock.patch('oscar.apps.checkout.session.Repository')
    def test_redirects_customers_when_no_shipping_methods_available(self,
                                                                    mock_repo):
        self.add_product_to_basket()
        self.enter_guest_details()
        self.enter_shipping_address()

        # Ensure no shipping methods available
        instance = mock_repo.return_value
        instance.get_shipping_methods.return_value = []

        response = self.get(reverse('checkout:index'))
        self.assertRedirectsTo(response, 'checkout:shipping-address')

    @mock.patch('oscar.apps.checkout.session.Repository')
    def test_redirects_customers_when_only_one_shipping_method_is_available(
            self, mock_repo):
        self.add_product_to_basket()
        self.enter_guest_details()
        self.enter_shipping_address()

        # Ensure one shipping method available
        instance = mock_repo.return_value
        instance.get_shipping_methods.return_value = [methods.Free()]

        response = self.get(reverse('checkout:index'))
        self.assertRedirectsTo(response, 'checkout:preview')


@override_settings(OSCAR_ALLOW_ANON_CHECKOUT=True)
class TestIdentifyUserView(CheckoutMixin, WebTestCase):
    is_anonymous = True

    def setUp(self):
        reload_url_conf()
        super(TestIdentifyUserView, self).setUp()

    def test_redirects_new_customers_to_registration_page(self):
        self.add_product_to_basket()
        page = self.get(reverse('checkout:identify-user'))

        form = page.form
        form['options'].select(GatewayForm.NEW)
        new_user_email = 'newcustomer@test.com'
        form['username'].value = new_user_email
        response = form.submit()

        expected_url = '{register_url}?next={forward}&email={email}'.format(
            register_url=reverse('customer:register'),
            forward='/checkout/',
            email=urlquote(new_user_email))
        self.assertRedirects(response, expected_url)

    def test_redirects_existing_customers_to_shipping_address_page(self):
        existing_user = User.objects.create_user(
            username=self.username, email=self.email, password=self.password)
        self.add_product_to_basket()
        page = self.get(reverse('checkout:identify-user'))
        form = page.form
        form.select('options', GatewayForm.EXISTING)
        form['username'].value = existing_user.email
        form['password'].value = self.password
        response = form.submit()
        self.assertRedirectsTo(response, 'checkout:shipping-address')

    def test_redirects_guest_customers_to_shipping_address_page(self):
        self.add_product_to_basket()
        response = self.enter_guest_details()
        self.assertRedirectsTo(response, 'checkout:shipping-address')

    def test_prefill_form_with_email_for_returning_guest(self):
        self.add_product_to_basket()
        email = 'forgetfulguest@test.com'
        self.enter_guest_details(email)
        page = self.get(reverse('checkout:identify-user'))
        self.assertEqual(email, page.form['username'].value)


@override_settings(OSCAR_ALLOW_ANON_CHECKOUT=True)
class TestShippingAddressView(CheckoutMixin, WebTestCase):
    is_anonymous = True

    def setUp(self):
        reload_url_conf()
        super(TestShippingAddressView, self).setUp()

    def test_shows_initial_data_if_the_form_has_already_been_submitted(self):
        self.add_product_to_basket()
        self.enter_guest_details('hello@egg.com')
        self.enter_shipping_address()
        page = self.get(reverse('checkout:shipping-address'), user=self.user)
        self.assertEqual('John', page.form['first_name'].value)
        self.assertEqual('Doe', page.form['last_name'].value)
        self.assertEqual('1 Egg Road', page.form['line1'].value)
        self.assertEqual('Shell City', page.form['line4'].value)
        self.assertEqual('N12 9RT', page.form['postcode'].value)


@override_settings(OSCAR_ALLOW_ANON_CHECKOUT=True)
class TestShippingMethodView(CheckoutMixin, WebTestCase):
    is_anonymous = True

    def setUp(self):
        reload_url_conf()
        super(TestShippingMethodView, self).setUp()

    @mock.patch('oscar.apps.checkout.session.Repository')
    def test_shows_form_when_multiple_shipping_methods_available(self,
                                                                 mock_repo):
        self.add_product_to_basket()
        self.enter_guest_details()
        self.enter_shipping_address()

        # Ensure multiple shipping methods available
        method = mock.MagicMock()
        method.code = 'm'
        instance = mock_repo.return_value
        instance.get_shipping_methods.return_value = [methods.Free(), method]
        form_page = self.get(reverse('checkout:index')).follow()
        self.assertEqual(urlsplit(form_page.request.url)[2],
                         reverse('checkout:shipping-method'))
        self.assertIsOk(form_page)

        response = form_page.forms[0].submit()
        self.assertRedirectsTo(response, 'checkout:preview')

    @mock.patch('oscar.apps.checkout.session.Repository')
    def test_check_user_can_submit_only_valid_shipping_method(self, mock_repo):
        self.add_product_to_basket()
        self.enter_guest_details()
        self.enter_shipping_address()
        method = mock.MagicMock()
        method.code = 'm'
        instance = mock_repo.return_value
        instance.get_shipping_methods.return_value = [methods.Free(), method]
        form_page = self.get(reverse('checkout:shipping-method'))
        # a malicious attempt?
        form_page.forms[0]['method_code'].value = 'super-free-shipping'
        response = form_page.forms[0].submit()
        self.assertRedirectsTo(response, 'checkout:shipping-method')


@override_settings(OSCAR_ALLOW_ANON_CHECKOUT=True)
class TestPaymentDetailsView(CheckoutMixin, WebTestCase):
    is_anonymous = True

    def setUp(self):
        reload_url_conf()
        super(TestPaymentDetailsView, self).setUp()

    @mock.patch('oscar.apps.checkout.views.PaymentDetailsView.handle_payment')
    def test_redirects_customers_when_using_bank_gateway(self, handle_payment):

        bank_url = 'https://bank-website.com'
        e = RedirectRequired(url=bank_url)
        handle_payment.side_effect = e
        preview = self.ready_to_place_an_order(is_guest=True)
        bank_redirect = preview.forms['place_order_form'].submit()
        self.assertRedirects(bank_redirect, bank_url)

    @mock.patch('oscar.apps.checkout.views.PaymentDetailsView.handle_payment')
    def test_handles_anticipated_payments_errors_gracefully(self,
                                                            handle_payment):
        msg = 'Submitted expiration date is wrong'
        e = UnableToTakePayment(msg)
        handle_payment.side_effect = e
        preview = self.ready_to_place_an_order(is_guest=True)
        response = preview.forms['place_order_form'].submit().follow()
        self.assertIsOk(response)
        # check user is warned
        response.mustcontain(msg)
        # check basket is restored
        basket = Basket.objects.get()
        self.assertEqual(basket.status, Basket.OPEN)

    @mock.patch('oscar.apps.checkout.mixins.logger')
    @mock.patch('oscar.apps.checkout.views.PaymentDetailsView.handle_payment')
    def test_handles_unexpected_payment_errors_gracefully(
            self, handle_payment, mock_logger):
        msg = 'This gateway is down for maintenance'
        e = PaymentError(msg)
        handle_payment.side_effect = e
        preview = self.ready_to_place_an_order(is_guest=True)
        response = preview.forms['place_order_form'].submit().follow()
        self.assertIsOk(response)
        # check user is warned with a generic error
        response.mustcontain(
            'A problem occurred while processing payment for this order',
            no=[msg])
        # admin should be warned
        self.assertTrue(mock_logger.error.called)
        # check basket is restored
        basket = Basket.objects.get()
        self.assertEqual(basket.status, Basket.OPEN)

    @mock.patch('oscar.apps.checkout.mixins.logger')
    @mock.patch('oscar.apps.checkout.views.PaymentDetailsView.handle_payment')
    def test_handles_bad_errors_during_payments(
            self, handle_payment, mock_logger):
        e = Exception()
        handle_payment.side_effect = e
        preview = self.ready_to_place_an_order(is_guest=True)
        response = preview.forms['place_order_form'].submit().follow()
        self.assertIsOk(response)
        self.assertTrue(mock_logger.error.called)
        basket = Basket.objects.get()
        self.assertEqual(basket.status, Basket.OPEN)

    @mock.patch('oscar.apps.checkout.flow.logger')
    @mock.patch('oscar.apps.checkout.mixins.Clerk.place_order')
    def test_handles_unexpected_order_placement_errors_gracefully(
            self, place_order, mock_logger):
        e = UnableToPlaceOrder()
        place_order.side_effect = e
        preview = self.ready_to_place_an_order(is_guest=True)
        response = preview.forms['place_order_form'].submit().follow()
        self.assertIsOk(response)
        self.assertTrue(mock_logger.error.called)
        basket = Basket.objects.get()
        self.assertEqual(basket.status, Basket.OPEN)


@override_settings(OSCAR_ALLOW_ANON_CHECKOUT=True)
class TestPlacingOrder(CheckoutMixin, WebTestCase):
    is_anonymous = True

    def setUp(self):
        reload_url_conf()
        super(TestPlacingOrder, self).setUp()

    def test_saves_guest_email_with_order(self):
        preview = self.ready_to_place_an_order(is_guest=True)
        thank_you = preview.forms['place_order_form'].submit().follow()
        order = thank_you.context['order']
        self.assertEqual('hello@egg.com', order.guest_email)
