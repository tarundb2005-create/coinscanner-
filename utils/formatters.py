def format_volume(num):
    if num is None:
        return "0"
    try:
        num = float(num)
    except:
        return "0"

    if num >= 1_00_000_00_00_000:
        return f"₹{num / 1_00_000_00_00_000:.2f} L.Cr"
    if num >= 1_00_00_000:
        return f"₹{num / 1_00_00_000:.2f} Cr"
    if num >= 1_00_000:
        return f"₹{num / 1_00_000:.2f} L"
    if num >= 1_000:
        return f"₹{num / 1_000:.2f} K"

    return f"₹{int(num)}"


def format_mcap(num):
    if num is None or num == 0:
        return "—"

    try:
        num = float(num)
    except:
        return "—"

    LAKH_CR = 1_00_000_00_00_000

    if num >= LAKH_CR:
        return f"₹{num / LAKH_CR:.2f} L.Cr"

    if num >= 1_00_00_000:
        cr = num / 1_00_00_000
        return f"₹{cr:,.0f} Cr" if cr >= 1000 else f"₹{cr:.1f} Cr"

    return "—"


def format_inr(num):
    if num is None:
        return "0"

    try:
        num = float(num)
    except:
        return "0"

    s = f"{num:,.2f}"

    integer, decimal = s.split(".")
    integer = integer.replace(",", "")

    if len(integer) <= 3:
        return f"{integer}.{decimal}"

    last3 = integer[-3:]
    rest = integer[:-3]

    chunks = []

    while len(rest) > 2:
        chunks.insert(0, rest[-2:])
        rest = rest[:-2]

    if rest:
        chunks.insert(0, rest)

    return f"{','.join(chunks)},{last3}.{decimal}"