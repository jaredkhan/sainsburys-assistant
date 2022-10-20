import pytest

from evaluate_math import evaluate_math_expression


@pytest.mark.parametrize("expression,expected_value", [
    ("1+2+3", 6),
    ("4/5", 0.8)
])
def test_can_evaluate_math_expression(expression, expected_value):
    assert evaluate_math_expression(expression) == expected_value
