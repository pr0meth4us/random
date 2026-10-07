"""Look up the Cambodian mobile operator that owns a number's prefix.

Prefix allocation only -- Cambodia has mobile number portability, so a ported
number still reports its original allocation here. Treat the result as "likely
carrier", not ground truth.
"""
import re

PREFIXES = {
    "Smart": ["010", "015", "016", "069", "070", "081", "086", "087", "093", "096", "098"],
    "Cellcard": ["011", "012", "014", "017", "061", "076", "077", "078", "085", "089", "092", "095", "099"],
    "Metfone": ["031", "060", "066", "067", "068", "071", "088", "090", "097"],
    "qb": ["013", "080", "083", "084"],
    "SEATEL": ["018"],
    "CooTel": ["038"],
}

_BY_PREFIX = {p: carrier for carrier, prefixes in PREFIXES.items() for p in prefixes}


def to_local(phone):
    """Normalize any format (+855.., 855.., 0..) to local 0-prefixed digits."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("855"):
        digits = digits[3:]
    return "0" + digits.lstrip("0")


def carrier_of(phone):
    """Return the operator name, or None if the prefix isn't allocated."""
    return _BY_PREFIX.get(to_local(phone)[:3])


def group_by_carrier(phones):
    """Bucket an iterable of numbers into {carrier: [phone, ...]}, unknown under None."""
    groups = {}
    for phone in phones:
        groups.setdefault(carrier_of(phone), []).append(phone)
    return groups


if __name__ == "__main__":
    assert carrier_of("016123456") == "Smart"
    assert carrier_of("+85516123456") == "Smart"
    assert carrier_of("85512345678") == "Cellcard"
    assert carrier_of("0313123456") == "Metfone"
    assert carrier_of("0999999999") is None or carrier_of("099123456") == "Cellcard"
    assert to_local("+855 96 123 4567") == "0961234567"
    assert group_by_carrier(["012111111", "016222222"]) == {
        "Cellcard": ["012111111"], "Smart": ["016222222"]
    }
    print("kh_carriers self-check passed")
