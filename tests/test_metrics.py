import math

from vts.metrics import percent_change, rmse


def test_rmse():
    assert math.isclose(rmse([1, 2, 3], [1, 2, 4]), math.sqrt(1 / 3))


def test_percent_change():
    assert math.isclose(percent_change(0.392, 0.387), (0.392 - 0.387) / 0.387 * 100)
