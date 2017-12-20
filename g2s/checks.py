import os
from urlparse import urlparse
import logging
logger = logging.getLogger(__name__)

def check_dir(directory, create=False):
    '''
    Check if a directory exists.
    If create, the directory is created if it does not exist.
    '''
    if not os.path.isdir(directory):
        logger.info("Directory does not exist: %s", directory)
        if create:
            logger.info("Create directory %s", directory)
            os.makedirs(directory)
            return True
        else:
            return False
    else:
        logger.info("Directory exists: %s", directory)
        return True


def check_file(path):
    '''
    Check if a file exists.
    '''
    return os.path.isfile(path)
        

def check_writable(path):
    '''
    Check if a file or directory is writable.
    '''
    return os.access(path, os.W_OK)


def check_url(url):
    '''
    Check if a URL is well formed.
    '''
    parsed_url = urlparse(url)
    if not [parsed_url.scheme, parsed_url.netloc, parsed_url.path]:
        return False
    else:
        return True

