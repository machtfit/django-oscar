from decimal import Decimal as D

from django.test import TestCase

from oscar.apps.offer import custom, models
from oscar.apps.offer.utils import SetOfLines
from oscar.test.offer import add_line


class TotalIsNearPi(models.Condition):

    class Meta:
        proxy = True

    def is_satisfied(self, set_of_lines):
        if (sum(line.price * line.quantity for line in set_of_lines)
                == D('3.14')):
            return True
        return False


class TestCustomCondition(TestCase):

    def setUp(self):
        self.condition = custom.create_condition(TotalIsNearPi)
        self.set_of_lines = SetOfLines([])

    def test_is_satisfied_by_matching_set_of_lines(self):
        add_line(self.set_of_lines, D('1.12'), 1)
        add_line(self.set_of_lines, D('1.01'), 2)
        self.assertTrue(self.condition.proxy().is_satisfied(self.set_of_lines))

    def test_is_not_satified_by_non_matching_set_of_lines(self):
        add_line(self.set_of_lines, D('1.12'), 2)
        add_line(self.set_of_lines, D('1.01'), 2)
        self.assertFalse(self.condition.proxy().is_satisfied(self.set_of_lines))
