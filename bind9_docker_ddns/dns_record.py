docker_source_id = "docker"
static_source_id = "static"


class DNSRecord:
    _bind_template = "{name}     IN  {record_type}       {value}"

    def __init__(self, zone, name, record_type, value, ttl=60, source=docker_source_id):
        self.zone = zone
        self.name = name
        self.record_type = record_type
        self.value = value
        self.ttl = ttl
        self.source = source

    def bind_record(self):
        return self._bind_template.format(name=self.name, record_type=self.record_type, value=self.value)

    def __repr__(self):
        return f'{self.name}: {self.record_type},{self.value} ttl: {self.ttl} zone: {self.zone} source: {self.source}'
