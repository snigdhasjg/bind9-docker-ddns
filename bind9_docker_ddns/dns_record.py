docker_source_id = "docker"
static_source_id = "static"


class DNSRecord:
    _template = "{name}     IN  {record_type}       {value} ; {source}"

    def __init__(self, zone, name, record_type, value, ttl=60, source=docker_source_id):
        self.zone = zone
        self.name = name
        self.record_type = record_type
        self.value = value
        self.ttl = ttl
        self.source = source

    def __repr__(self):
        return self._template.format(name=self.name, record_type=self.record_type, value=self.value, source=self.source)
