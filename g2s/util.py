import os
import string
import logging
logger = logging.getLogger(__name__)

def format_filename(s):
    '''
    Take a string and return a valid filename constructed from the string.
    Uses a whitelist approach: any characters not present in valid_chars are
    removed. Also spaces are replaced with underscores.
     
    Note: this method may produce invalid filenames such as ``, `.` or `..`
    When I use this method I prepend a date string like '2009_01_15_19_46_32_'
    and append a file extension like '.txt', so I avoid the potential of using
    an invalid filename.

    This is copied from:
    https://gist.github.com/seanh/93666
    '''
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    filename = ''.join(c for c in s if c in valid_chars)
    filename = filename.replace(' ','_') # I don't like spaces in filename
    return filename


def unflatten(d, sep='|'):
    '''
    Unflatten a dictionary
    e.g. unflatten({'a' : 0, 'c|d' : 1)) -> {'a' : 0, 'c' : {'d' : 1}}
    '''
    resultDict = dict()
    for key, value in d.iteritems():
        parts = key.split(sep)
        d = resultDict
        for part in parts[:-1]:
            if part not in d:
                d[part] = dict()
            d = d[part]
        d[parts[-1]] = value
    return resultDict

