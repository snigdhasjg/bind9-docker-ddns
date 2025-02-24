docker_source_id = "docker"
static_source_id = "static"

import logging

LOG = logging.getLogger(__name__)

class DNSRecord:
    _bind_template = "{name}     IN  {record_type}       {value}"

    def __init__(self, zone, name, record_type, value, ttl=60, source=docker_source_id):
        self.zone = zone
        self.name = name
        self.record_type = record_type
        self.value = value
        self.ttl = ttl
        self.source = source

    def __repr__(self):
        return f'{self.name}: {self.record_type},{self.value} ttl: {self.ttl} zone: {self.zone} source: {self.source}'

    def bind_record(self):
        return self._bind_template.format(name=self.name, record_type=self.record_type, value=self.value)

    def arpa_record(self, reverse_zone):
        if not reverse_zone:
            return

        if self.record_type != 'A':
            return

        ip_reverse = '.'.join(reversed(self.value.split('.')))
        reverse_zone_ip_section = reverse_zone.removesuffix('.in-addr.arpa')
        ip_reverse_prefix = ip_reverse.removesuffix(f'.{reverse_zone_ip_section}')

        if ip_reverse == ip_reverse_prefix:
            LOG.debug("IP doesn't belong to ARPA zone")
            return None

        return DNSRecord(reverse_zone, ip_reverse_prefix, 'PTR', f'{self.name}.{self.zone}.', ttl=self.ttl, source=self.source)
