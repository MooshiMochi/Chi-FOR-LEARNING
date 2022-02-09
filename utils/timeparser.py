import re
import time as date  # Note: time.time() is UTC seconds from Jan 1 1970
from datetime import datetime


TIMES = {
    'y': 31536000,
    'mo': 2628000,
    'w': 604800,
    'd': 86400,
    'h': 3600,
    'm': 60,
    's': 1
}

SHORT_UNITS = {
    'w': 'week',
    'd': 'day',
    'h': 'hour',
    'm': 'minute',
    's': 'second'
}

SHORT_UNITS_EX = {
    'y': 'year',
    'mo': 'month',
    'w': 'week',
    'd': 'day',
    'h': 'hour',
    'm': 'minute',
    's': 'second'
}

LONG_UNITS = {
    'year': 'y',
    'month': 'mo',
    'week': 'w',
    'day': 'd',
    'hour': 'h',
    'minute': 'm',
    'second': 's'
}

SHORT_TIME_RX = re.compile('^[0-9]+[smhdw]', re.IGNORECASE)
LONG_TIME_RX = re.compile('^([0-9]+) *(s(?:ec(?:ond(?:s)?)?)?|m(?:in(?:ute(?:s)?)?)?|h(?:our(?:s)?)?|d(?:ay(?:s)?)?|w(?:eek(?:s)?)?)', re.IGNORECASE)
MULTI_TIME_RX = re.compile('(?:([0-9]+)(mo|[smhdwy]))*?', re.IGNORECASE)


class TimeFormat:
    __slots__ = ('absolute', 'relative', 'amount', 'unit', 'full_unit', 'humanized', 'as_date')

    def __init__(self, absolute: int, relative: int, amount: int, unit: str, human: str, date: datetime):
        self.absolute = absolute
        self.relative = relative
        self.amount = amount
        self.unit = f'{unit}{"s" if amount != 1 else ""}'
        self.full_unit = SHORT_UNITS.get(unit, unit)
        self.humanized = human
        self.as_date = date

    def __str__(self):
        plural = '' if self.amount == 1 else 's'
        return f'{self.amount} {self.full_unit}{plural}'


def convert(text: str):
    match = SHORT_TIME_RX.search(text)

    if not match:
        return None, text

    content = match.group()
    start = match.span()[1]

    time = int(content[:-1])
    unit = content[-1].lower()
    formal_unit = SHORT_UNITS[unit]

    relative = TIMES[unit] * time
    absolute = int(round(date.time())) + relative
    human = datetime.fromtimestamp(absolute).strftime("%d-%m-%y %H:%M:%S")

    return TimeFormat(absolute, relative, time, formal_unit, human, human), text[start:].strip()


def parse(text: str):
    match = LONG_TIME_RX.match(text)

    if not match:
        return None

    time = int(match.group(1))
    unit = match.group(2).lower()[0]

    relative = TIMES[unit] * time
    absolute = int(round(date.time())) + relative
    human = datetime.fromtimestamp(absolute).strftime("%d-%m-%y %H:%M:%S")

    return TimeFormat(absolute, relative, time, unit, human, human)


def parse_time_ex(inp: str) -> str:
    matcher = MULTI_TIME_RX.findall(inp)

    if not matcher:
        raise Exception('Invalid string')

    t = {}
    relative = 0

    for match in matcher:
        if any(len(group) == 0 for group in match):
            continue

        full = SHORT_UNITS_EX[match[1]]
        if full not in t:
            t[full] = 0

        n = int(match[0])
        t[full] += n
        relative += TIMES[match[1]] * n

    human = ''
    for v in SHORT_UNITS_EX.values():  # Iterate over units to ensure we can parse the final result in the expected order.
        if v not in t:
            continue

        n = '' if t[v] == 1 else 's'
        human += f'{t[v]} {v}{n} '

    absolute = int(round(date.time())) + relative
    as_date = datetime.fromtimestamp(absolute).strftime('%d-%m-%y %H:%M:%S')
    return TimeFormat(absolute, relative, relative, 'seconds', human, as_date)
