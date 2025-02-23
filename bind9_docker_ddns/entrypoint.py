import logging
import time

from bind9_docker_ddns.bind import Bind
from bind9_docker_ddns.config import Config
from bind9_docker_ddns.container import Container
from bind9_docker_ddns.dns_record import DNSRecord, static_source_id

LOG = logging.getLogger(__name__)


def main():
    config = Config()
    bind = Bind(config)
    container = Container(config)

    for each_record in config.static_dns_records:
        bind.add(each_record)

    while True:
        LOG.info('Managed DNS entries: %s', bind.list_docker_records(config.zone))
        container_list = container.list()
        LOG.info('Containers: %s', container_list)
        [bind.add(container) for container in container_list]
        time.sleep(60)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
