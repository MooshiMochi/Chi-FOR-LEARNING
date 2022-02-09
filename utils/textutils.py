from urllib.parse import quote

import aiohttp
import numpy as np

_headers = {
    'User-Agent': 'Chi (https://github.com/Devoxin/Chi)',
    'Content-Type': 'application/x-www-form-urlencoded'
}


class AnsiFormat:
    #_COLOURS = [AnsiFormat.black, AnsiFormat.red, AnsiFormat.green, AnsiFormat.yellow, AnsiFormat.blue, AnsiFormat.magenta, AnsiFormat.cyan, AnsiFormat.white]

    @staticmethod
    def _print(colour, text):
        return f'[{colour}m{text}[0m'

    @staticmethod
    def black(t: str):
        return AnsiFormat._print(30, t)

    @staticmethod
    def red(t: str):
        return AnsiFormat._print(31, t)

    @staticmethod
    def green(t: str):
        return AnsiFormat._print(32, t)

    @staticmethod
    def yellow(t: str):
        return AnsiFormat._print(33, t)

    @staticmethod
    def blue(t: str):
        return AnsiFormat._print(34, t)

    @staticmethod
    def magenta(t: str):
        return AnsiFormat._print(35, t)

    @staticmethod
    def cyan(t: str):
        return AnsiFormat._print(36, t)

    @staticmethod
    def white(t: str):
        return AnsiFormat._print(37, t)

# TODO: Backgrounds
#        [30m   BLACK [31m     RED [32m   GREEN [33m  YELLOW [34m    BLUE [35m MAGENTA [36m    CYAN [37m   WHITE[0m
# [40m  BLACK[0m[40m[30m   BLACK [31m     RED [32m   GREEN [33m  YELLOW [34m    BLUE [35m MAGENTA [36m    CYAN [37m   WHITE [0m[0m
# [41m    RED[0m[41m[30m   BLACK [31m     RED [32m   GREEN [33m  YELLOW [34m    BLUE [35m MAGENTA [36m    CYAN [37m   WHITE [0m[0m
# [42m  GREEN[0m[42m[30m   BLACK [31m     RED [32m   GREEN [33m  YELLOW [34m    BLUE [35m MAGENTA [36m    CYAN [37m   WHITE [0m[0m
# [43m YELLOW[0m[43m[30m   BLACK [31m     RED [32m   GREEN [33m  YELLOW [34m    BLUE [35m MAGENTA [36m    CYAN [37m   WHITE [0m[0m
# [44m   BLUE[0m[44m[30m   BLACK [31m     RED [32m   GREEN [33m  YELLOW [34m    BLUE [35m MAGENTA [36m    CYAN [37m   WHITE [0m[0m
# [45mMAGENTA[0m[45m[30m   BLACK [31m     RED [32m   GREEN [33m  YELLOW [34m    BLUE [35m MAGENTA [36m    CYAN [37m   WHITE [0m[0m
# [46m   CYAN[0m[46m[30m   BLACK [31m     RED [32m   GREEN [33m  YELLOW [34m    BLUE [35m MAGENTA [36m    CYAN [37m   WHITE [0m[0m
# [47m  WHITE[0m[47m[30m   BLACK [31m     RED [32m   GREEN [33m  YELLOW [34m    BLUE [35m MAGENTA [36m    CYAN [37m   WHITE [0m[0m


def paginate(text: str, limit: int = 2000):
    """ Slices text into chunks to make it manageable """
    lines = text.split('\n')
    pages = []

    chunk = ''
    for line in lines:
        if len(chunk) + len(line) > limit and len(chunk) > 0:
            pages.append(chunk)
            chunk = ''

        if len(line) > limit:
            _lchunks = len(line) / limit
            for _lchunk in range(int(_lchunks)):
                s = limit * _lchunk
                e = s + limit
                pages.append(line[s:e])
        else:
            chunk += line + '\n'

    if chunk:
        pages.append(chunk)

    return pages


async def dump(content: str):
    async with aiohttp.request('POST', 'https://hastepaste.com/api/create',
                               data=f'raw=false&text={quote(content)}', headers=_headers) as res:
        return await res.text() if res.status >= 200 and res.status < 400 else None


def levenshtein_distance(s, t, ratio_calc = False):
    """ levenshtein_distance:
        Calculates levenshtein distance between two strings.
        If ratio_calc = True, the function computes the
        levenshtein distance ratio of similarity between two strings
        For all i and j, distance[i,j] will contain the Levenshtein
        distance between the first i characters of s and the
        first j characters of t
    """
    # Initialize matrix of zeros
    rows = len(s) + 1
    cols = len(t) + 1
    distance = np.zeros((rows,cols), dtype = int)

    # Populate matrix of zeros with the indeces of each character of both strings
    for i in range(1, rows):
        for k in range(1,cols):
            distance[i][0] = i
            distance[0][k] = k

    # Iterate over the matrix to compute the cost of deletions,insertions and/or substitutions    
    for col in range(1, cols):
        for row in range(1, rows):
            if s[row - 1] == t[col - 1]:
                cost = 0 # If the characters are the same in the two strings in a given position [i,j] then the cost is 0
            else:
                # In order to align the results with those of the Python Levenshtein package, if we choose to calculate the ratio
                # the cost of a substitution is 2. If we calculate just distance, then the cost of a substitution is 1.
                if ratio_calc:
                    cost = 2
                else:
                    cost = 1
            distance[row][col] = min(distance[row-1][col] + 1,      # Cost of deletions
                                 distance[row][col-1] + 1,          # Cost of insertions
                                 distance[row-1][col-1] + cost)     # Cost of substitutions
    if ratio_calc:
        # Computation of the Levenshtein Distance Ratio
        ratio = ((len(s)+len(t)) - distance[row][col]) / (len(s)+len(t))
        return ratio
    else:
        # print(distance) # Uncomment if you want to see the matrix showing how the algorithm computes the cost of deletions,
        # insertions and/or substitutions
        # This is the minimum number of edits needed to convert string a to string b
        return distance[row][col]


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
