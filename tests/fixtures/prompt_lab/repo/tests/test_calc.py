import unittest

from calc import clamp, mean, median


class MeanTests(unittest.TestCase):
    def test_mean_of_three(self) -> None:
        self.assertEqual(mean([1.0, 2.0, 6.0]), 3.0)

    def test_mean_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            mean([])


class ClampTests(unittest.TestCase):
    def test_clamp_inside_range(self) -> None:
        self.assertEqual(clamp(5.0, 1.0, 10.0), 5.0)

    def test_clamp_below_low(self) -> None:
        self.assertEqual(clamp(-3.0, 1.0, 10.0), 1.0)

    def test_clamp_above_high(self) -> None:
        self.assertEqual(clamp(42.0, 1.0, 10.0), 10.0)


class MedianTests(unittest.TestCase):
    def test_median_odd(self) -> None:
        self.assertEqual(median([9.0, 1.0, 5.0]), 5.0)

    def test_median_even(self) -> None:
        self.assertEqual(median([4.0, 1.0, 3.0, 2.0]), 2.5)


if __name__ == "__main__":
    unittest.main()
