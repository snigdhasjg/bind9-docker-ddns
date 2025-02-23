import logging

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)

MAIN_LOGGER = logging.getLogger('__main__')
MAIN_LOGGER.setLevel(logging.INFO)

logging.basicConfig(level=logging.INFO)