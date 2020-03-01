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
            for _lchunk in range(_lchunks):
                s = limit * _lchunk
                e = s + limit
                pages.append(line[s:e])
        else:
            chunk += line + '\n'

    if chunk:
        pages.append(chunk)

    return pages
