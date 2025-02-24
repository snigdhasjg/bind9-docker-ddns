import logging
import time

from bind9_docker_ddns.bind import Bind
from bind9_docker_ddns.config import Config
from bind9_docker_ddns.container import Container

LOG = logging.getLogger(__name__)


def main():
    config = Config()
    bind = Bind(config)
    container = Container(config)

    managed_records = bind.list(config.zone)
    LOG.info('Managed DNS entries: %s', managed_records)
    if config.reverse_zone:
        reverse_managed_records = bind.list(config.reverse_zone)
        LOG.info('Managed reverse static DNS entries: %s', reverse_managed_records)
    else:
        reverse_managed_records = dict()

    for each_record in config.static_dns_records:
        bind.add(each_record)

        if config.reverse_zone:
            bind.add(each_record.arpa_record(config.reverse_zone))

    while True:
        container_list = container.list()
        LOG.info('Containers: %s', container_list)
        [bind.add(container) for container in container_list]

        time.sleep(60)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
