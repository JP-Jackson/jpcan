"""Display-time unit conversion. Profiles store native units."""

IMPERIAL = {
    "km/h": ("mph", lambda v: v * 0.621371),
    "km": ("mi", lambda v: v * 0.621371),
    "°C": ("°F", lambda v: v * 9 / 5 + 32),
    "kPa": ("psi", lambda v: v * 0.145038),
    "kPaa": ("psia", lambda v: v * 0.145038),   # absolute
    "kPag": ("psig", lambda v: v * 0.145038),   # gauge (above atmosphere)
    "bar": ("psi", lambda v: v * 14.5038),
    "barg": ("psig", lambda v: v * 14.5038),   # gauge
    "L/h": ("gal/h", lambda v: v * 0.264172),
    "L": ("gal", lambda v: v * 0.264172),
    "km/L": ("mpg", lambda v: v * 2.35215),
}


def display(value: float, units: str, imperial: bool = True) -> tuple[float, str]:
    if imperial and units in IMPERIAL:
        u, f = IMPERIAL[units]
        return f(value), u
    return value, units
