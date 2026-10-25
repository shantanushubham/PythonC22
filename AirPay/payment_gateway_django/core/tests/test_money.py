from decimal import Decimal

from django.test import SimpleTestCase

from core.money import AmountError, format_amount, parse_amount


class ParseAmountTests(SimpleTestCase):
    def test_strings_and_numbers(self):
        self.assertEqual(parse_amount("1500.50"), 150050)
        self.assertEqual(parse_amount("99.5"), 9950)
        self.assertEqual(parse_amount("1"), 100)
        self.assertEqual(parse_amount(10), 1000)
        self.assertEqual(parse_amount(Decimal("0.01")), 1)

    def test_rejects_bad_values(self):
        for value in [None, "", "0", "-1", "1.234", "abc", True, "10000000.01", 0]:
            with self.subTest(value=value):
                with self.assertRaises(AmountError):
                    parse_amount(value)

    def test_format(self):
        self.assertEqual(format_amount(150050), "1500.50")
        self.assertEqual(format_amount(1), "0.01")
        self.assertEqual(format_amount(0), "0.00")
