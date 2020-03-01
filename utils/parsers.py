def as_number(num, default):
    try:
        return float(num)
    except ValueError:
        return default


def time_string(time):
    h, r = divmod(int(time.total_seconds()), 3600)
    m, s = divmod(r, 60)
    d, h = divmod(h, 24)

    return "%02d:%02d:%02d:%02d" % (d, h, m, s)
