import logging

import docker

from bind9_docker_ddns.config import Config
from bind9_docker_ddns.dns_record import DNSRecord

LOG = logging.getLogger(__name__)


class Container:
    def __init__(self, config: Config):
        self.config = config
        self.client = docker.from_env()

    def list(self):
        dns_records = []
        container_list = self.client.containers.list()
        for container in container_list:
            container_name = container.attrs['Name'][1:]

            hostname = container.labels.get(self.config.container_hostname_label)
            if not hostname:
                LOG.warning("No hostname label present for container %s, ignoring...", container_name)
                continue

            record_type = container.labels.get(self.config.container_record_type_label)
            if record_type:
                value = container.labels.get(self.config.container_value_label)
                if value:
                    dns_record = DNSRecord(hostname, record_type, value)
                else:
                    LOG.error("As %s label is specified for container %s but %s label not present, ignoring...",
                              self.config.container_record_type_label, container_name,
                              self.config.container_value_label)
                    continue
            else:
                container_network = container.labels.get(self.config.container_network_label)
                if container_network:
                    ip_address = container.attrs['NetworkSettings']['Networks'][container_network]['IPAddress']
                else:
                    ip_address = container.attrs['NetworkSettings']['IPAddress']
                    if not ip_address:
                        first_network_name = next(iter(container.attrs['NetworkSettings']['Networks']))
                        ip_address = container.attrs['NetworkSettings']['Networks'][first_network_name]['IPAddress']
                        if not ip_address:
                            LOG.warning("Not IP found for container %s, ignoring...", container_name)
                            continue

                dns_record = DNSRecord(hostname, 'A', ip_address)

            dns_records.append(dns_record)

        return dns_records

