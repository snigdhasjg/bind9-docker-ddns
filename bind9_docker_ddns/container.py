import logging

import docker

from bind9_docker_ddns.config import Config
from bind9_docker_ddns.dns_record import DNSRecord, docker_source_id

LOG = logging.getLogger(__name__)

HOSTNAME_LABEL_SUFFIX = "hostname"
RECORD_TYPE_LABEL_SUFFIX = "record-type"
RECORD_VALUE_LABEL_SUFFIX = "record-value"
DOCKER_NETWORK_LABEL_SUFFIX = "docker-network"

class Container:
    def __init__(self, config: Config):
        self.config = config
        self.client = docker.from_env()

    def list(self):
        dns_records = []
        container_list = self.client.containers.list()
        for container in container_list:
            dns_record = self._process_label(self.config.zone, container, f'{self.config.client_name}.{self.config.zone}')
            if dns_record:
                dns_records.append(dns_record)

        return dns_records

    @staticmethod
    def _process_label(zone, container, label_prefix):
        container_name = container.attrs['Name'][1:]

        hostname = container.labels.get(f'{label_prefix}.{HOSTNAME_LABEL_SUFFIX}')
        if not hostname:
            LOG.warning("No hostname label present for container %s, ignoring...", container_name)
            return

        record_type = container.labels.get(f'{label_prefix}.{RECORD_TYPE_LABEL_SUFFIX}')
        if record_type:
            value = container.labels.get(f'{label_prefix}.{RECORD_VALUE_LABEL_SUFFIX}')
            if value:
                return DNSRecord(zone, hostname, record_type, value, source=docker_source_id)
            else:
                LOG.error("As %s label is specified for container %s but %s label not present, ignoring...",
                          f'{label_prefix}.{RECORD_TYPE_LABEL_SUFFIX}',
                          container_name,
                          f'{label_prefix}.{RECORD_VALUE_LABEL_SUFFIX}')
                return

        container_network = container.labels.get(f'{label_prefix}.{DOCKER_NETWORK_LABEL_SUFFIX}')
        if container_network:
            ip_address = container.attrs['NetworkSettings']['Networks'][container_network]['IPAddress']
        else:
            ip_address = container.attrs['NetworkSettings']['IPAddress']
            if not ip_address:
                first_network_name = next(iter(container.attrs['NetworkSettings']['Networks']))
                ip_address = container.attrs['NetworkSettings']['Networks'][first_network_name]['IPAddress']
                if not ip_address:
                    LOG.warning("Not IP found for container %s, ignoring...", container_name)
                    return

        return DNSRecord(zone, hostname, 'A', ip_address, source=docker_source_id)
