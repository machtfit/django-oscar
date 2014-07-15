from decimal import Decimal as D

from django.test import TestCase

from oscar.apps.offer import models
from oscar.apps.offer.utils import SetOfLines
from oscar.test import factories
from oscar.test.offer import add_line


class TestAPercentageDiscount(TestCase):

    def setUp(self):
        range = models.Range(
            name="All products", includes_all_products=True)
        self.benefit = models.PercentageDiscountBenefit(
            range=range,
            type=models.Benefit.PERCENTAGE,
            value=20)
        self.set_of_lines = SetOfLines([])

    def test_gives_a_percentage_discount(self):
        add_line(self.set_of_lines, 12, 2)
        result = self.benefit.apply(self.set_of_lines)
        self.assertEqual(2 * 12 * D('0.2'), result.discount)
        self.assertEqual(2, self.set_of_lines.num_items_with_benefit)
        self.assertEqual(0, self.set_of_lines.num_items_without_benefit)

    def test_does_not_apply_to_empty_set_of_lines(self):
        result = self.benefit.apply(self.set_of_lines)
        self.assertFalse(result)
        self.assertEqual(0, self.set_of_lines.num_items_with_benefit)
        self.assertEqual(0, self.set_of_lines.num_items_without_benefit)

    def test_does_not_apply_to_non_discountable_products(self):
        product = factories.create_product(is_discountable=False)
        add_line(self.set_of_lines, 12, 2, product=product)
        result = self.benefit.apply(self.set_of_lines)
        self.assertFalse(result)
        self.assertEqual(0, self.set_of_lines.num_items_with_benefit)
        self.assertEqual(2, self.set_of_lines.num_items_without_benefit)

    def test_does_not_discount_more_than_max_affected_items_lines(self):
        self.benefit.max_affected_items = 1
        add_line(self.set_of_lines, 12, 1)
        add_line(self.set_of_lines, 14, 1)
        result = self.benefit.apply(self.set_of_lines)
        self.assertEqual(1 * 12 * D('0.2'), result.discount)
        self.assertEqual(1, self.set_of_lines.num_items_with_benefit)
        self.assertEqual(1, self.set_of_lines.num_items_without_benefit)

    def test_does_not_discount_more_than_max_total_discount(self):
        add_line(self.set_of_lines, 12, 2)
        add_line(self.set_of_lines, 10, 2)
        result = self.benefit.apply(self.set_of_lines,
                                    max_total_discount=3)
        self.assertLessEqual(result.discount, 3)

    def test_allows_overriding_discount_percentage(self):
        add_line(self.set_of_lines, 100, 1)
        result = self.benefit.apply(self.set_of_lines, discount_percent=30)
        self.assertEqual(result.discount, 30)
