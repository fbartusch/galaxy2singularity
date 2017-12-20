import sys
import logging as log

# Create logger

def create_logger(log_file, log_level):
    '''
    Create a basic logger that is also used in the submodules.
    '''

    log.basicConfig(filename=log_file, level=log.DEBUG)
    logFormatter = log.Formatter("%(asctime)s [%(levelname)-5.5s]  %(message)s")
    logger = log.getLogger()

    fileHandler = log.FileHandler(log_file, mode='w')
    fileHandler.setFormatter(logFormatter)
    logger.addHandler(fileHandler)

    consoleHandler = log.StreamHandler(sys.stdout)
    consoleHandler.setFormatter(logFormatter)
    logger.addHandler(consoleHandler)

    return logger
