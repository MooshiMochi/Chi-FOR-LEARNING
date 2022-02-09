from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile


def make_zip(contents):
    """
    Makes a ZIP file using the specified contents.
    
    Contents must be a tuple of (filename, bytesio-object).
    Returns a BytesIO object containing the zip data.
    """
    mem_buf = BytesIO()
    with ZipFile(mem_buf, 'w', ZIP_DEFLATED, False) as zf:
        for fn, data in contents:
            zf.writestr(fn, data.getvalue())

    return mem_buf
