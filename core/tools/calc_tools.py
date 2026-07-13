r"""
calc — deterministic, units-aware arithmetic FRIDAY calls instead of doing
math in her head.

Motivating failures (overnight regression run): a 14B slips on exactly the
work code does perfectly — it computed "40 W for 90 minutes" as 40*90 and
answered 3600-ish instead of 60 Wh, and treated "2 W for 1 hour" as 2*60.
The lesson from CLAUDE.md — "don't make the model do what code can do" — so
quantitative answers route through Pint here. Because Pint carries units
through the arithmetic, the classic minutes-vs-hours (x60) magnitude slip
becomes impossible: `2 W * 60 min` converted to `Wh` is 2, not 120, no matter
how she writes it.

This is a pure computation tool (kind="internal"): no disk, no network, no
gate. The evaluator is Pint's own expression parser (a restricted AST walk),
NOT Python eval — arbitrary code can't run through it.
"""

import pint

# One registry for the tool; independent of the graders' registry in tests.
_ureg = pint.UnitRegistry()


def register_calc_tools(registry):

    def calc(expression: str, to_unit: str = "") -> str:
        """Evaluate a units-aware expression, optionally converting the result.

        expression : e.g. "40 W * 90 min", "0.65 N*m * 20 * 0.8", "12 V / 4 ohm"
        to_unit    : optional target unit, e.g. "Wh", "N*m", "A"
        """
        expr = (expression or "").strip()
        if not expr:
            return "ERROR: empty expression."
        try:
            value = _ureg.parse_expression(expr)
        except Exception as e:
            return (f"ERROR: could not parse '{expr}' ({type(e).__name__}). "
                    f"Write it as a units expression, e.g. '40 W * 90 min' or "
                    f"'12 V / 4 ohm'.")
        target = to_unit.strip()
        if target:
            try:
                value = value.to(target)
            except pint.DimensionalityError as e:
                return (f"ERROR: '{expr}' is not compatible with '{target}' - {e}. "
                        f"Check the physics (or the parentheses: '12 V / 4 ohm' "
                        f"means (12 V / 4) * ohm; write '12 V / (4 ohm)').")
            except Exception:
                return (f"ERROR: '{target}' isn't a unit I recognize. Use a plain "
                        f"unit spelling, e.g. 'W', 'Wh', 'N*m', 'A', 'm/s'.")
        # Compact, unambiguous result the model can quote directly.
        try:
            mag = value.magnitude
            shown = f"{mag:.6g}"
            units = f"{value.units:~}" if hasattr(value, "units") else ""
        except Exception:
            return f"= {value}"
        return f"= {shown} {units}".strip()

    registry.register(
        "calc",
        # Examples are phrased as ARGUMENT VALUES, never as call syntax like
        # calc(...): the friday-tuned-v1 eval showed the model parroting this
        # description's example calls verbatim as its text reply (GOLD-ohm-01
        # failed with a reply that WAS the old example) instead of making the
        # structured call. Don't reintroduce an imitatable calling form here.
        "Compute a numeric result with UNITS carried through — use this for "
        "EVERY quantitative answer (arithmetic, unit conversion, a physics "
        "formula's final number) instead of calculating in your head. Put "
        "units inside the expression and it converts for you: expression "
        "'40 W * 90 min' with to_unit 'Wh' gives 60 Wh; expression "
        "'12 V / (4 ohm)' with to_unit 'A' gives 3 A. If the units don't "
        "match the target it tells you — that usually means the setup is "
        "wrong. Watch division precedence: put a denominator that has units "
        "in parentheses, '12 V / (4 ohm)', not '12 V / 4 ohm'.",
        {"type": "object", "properties": {
            "expression": {"type": "string", "description":
                           "Units expression, e.g. '40 W * 90 min' or '5 kg * 9.81 m/s**2'"},
            "to_unit": {"type": "string", "description":
                        "Optional target unit for the result, e.g. 'Wh', 'N*m', 'A'"}},
         "required": ["expression"]},
        calc,
        kind="internal",
    )
