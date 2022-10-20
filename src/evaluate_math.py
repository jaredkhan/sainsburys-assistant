import sys

import re

_re_math_expression = re.compile(rb'd([\x00-\xFF]+)S\x00')


def evaluate_math_expression(expr: str) -> float:
    try:
        code = compile(expr, 'userinput', 'eval')
    except SyntaxError:
        raise ValueError(f"Malformed expression: {expr}")
    match = _re_math_expression.fullmatch(code.co_code)
    if not match:
        raise ValueError(f"Not a simple algebraic expression: {expr}")
    try:
        return code.co_consts[int.from_bytes(match.group(1), sys.byteorder)]
    except IndexError:
        raise ValueError(f"Expression not evaluated as constant: {expr}")
