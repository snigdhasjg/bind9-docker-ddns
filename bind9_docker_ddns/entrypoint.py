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

    bind.add(DNSRecord(config.zone, "one", "A", "172.17.1.0", source=static_source_id))
    bind.add(DNSRecord(config.zone, "two", "A", "172.17.2.0", source=static_source_id))
    bind.add(DNSRecord(config.zone, "three", "A", "172.17.3.0", source=static_source_id))

    while True:
        LOG.info('Managed DNS entries: %s', bind.list_docker_records(config.zone))
        container_list = container.list()
        LOG.info('Containers: %s', container_list)
        [bind.add(container) for container in container_list]
        time.sleep(60)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
