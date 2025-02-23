import logging
import re
import socket
import subprocess
from pathlib import Path

import dns.query
import dns.resolver
import dns.tsigkeyring
import dns.update
import dns.zone

from bind9_docker_ddns.config import Config
from bind9_docker_ddns.dns_record import DNSRecord, docker_source_id

config_template = """
acl "trusted" {
  localhost;
  localnets;
  127.0.0.1;
  $trusted_cidrs
};

options {
    directory "/var/cache/bind";

    recursion yes;
    allow-query { trusted; };

    forwarders {
        $dns_forwarders
    };

    dnssec-validation auto;

    listen-on { any; };
    listen-on-v6 { any; };
};
"""

zone_configuration_template = """
zone "$zone_name" {
    type master;
    file "$zones_directory/$zone_name";

    update-policy {
        grant * zonesub ANY;
    };
};
"""

zone_definition_template = """
$TTL 86400	; 1 day
@       IN  SOA     $nameserver_hostname.$zone_name.    admin.$zone_name. (
                                                          3     ; Serial
                                                     604800     ; Refresh
                                                      86400     ; Retry
                                                    2419200     ; Expire
                                                     604800     ; Negative Cache TTL
                                                    )   
;
@       IN  NS      $nameserver_hostname.$zone_name.
"""

tsig_key_pattern = r'secret "(.*)";'

LOG = logging.getLogger(__name__)


def _start_bind():
    subprocess.call(['named', '-u', 'root'])


def _get_current_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 1))
    return s.getsockname()[0]


class Bind:
    def __init__(self, config: Config):
        self.config = config
        self.current_ip = _get_current_ip()

        tsig_key = self._setup_bind()
        self.keyring = dns.tsigkeyring.from_text({self.config.client_name: tsig_key})

        _start_bind()

    def _setup_bind(self):
        bind_home_directory = Path(self.config.bind_home)
        bind_home_directory.mkdir(parents=True, exist_ok=True)

        tsig_key_file = Path(bind_home_directory, f'{self.config.client_name}.key')

        init_file = Path(bind_home_directory, f'.{self.config.client_name}.init')
        if init_file.exists():
            LOG.error("Already initialized once, cleanup and start again")
            raise Exception("Already initialized once, cleanup and start again")
            # TODO: ability to skip if initialized, make sure the nameserver IP is same
            # tsig.key
            # with open(tsig_key_file, 'r') as f:
            #     tsig_key = f.read()
            #     return re.search(tsig_key_pattern, tsig_key).group(1)

        # config
        named_conf_options = config_template \
            .replace('$trusted_cidrs', '\n'.join(map(lambda x: f'{x};', self.config.trusted_cidrs))) \
            .replace('$dns_forwarders', '\n'.join(map(lambda x: f'{x};', self.config.dns_forwarders)))

        named_conf_options += f'include "{tsig_key_file.absolute().as_posix()}";\n'

        with open(Path(bind_home_directory, 'named.conf.options'), "w") as f:
            f.write(named_conf_options)

        # zone
        zone_configuration = zone_configuration_template \
            .replace("$zone_name", self.config.zone) \
            .replace("$zones_directory", bind_home_directory.absolute().as_posix())

        with open(Path(bind_home_directory, 'named.conf.local'), 'a+') as f:
            f.write(zone_configuration)

        zone_definition = zone_definition_template \
            .replace("$zone_name", self.config.zone) \
            .replace("$nameserver_hostname", self.config.nameserver_hostname)
        zone_definition += DNSRecord(self.config.zone, self.config.nameserver_hostname, "A", self.current_ip).bind_record()
        with open(Path(bind_home_directory, self.config.zone), 'w') as f:
            f.write(zone_definition)

        # reverse zone
        if self.config.reverse_zone:
            reverse_zone_configuration = zone_configuration_template \
                .replace("$zone_name", self.config.reverse_zone) \
                .replace("$zones_directory", bind_home_directory.absolute().as_posix())
            with open(Path(bind_home_directory, 'named.conf.local'), 'a+') as f:
                f.write(reverse_zone_configuration)

            reverse_zone_definition = zone_definition_template \
                .replace("$zone_name", self.config.zone) \
                .replace("$nameserver_hostname", self.config.nameserver_hostname)
            with open(Path(bind_home_directory, self.config.reverse_zone), 'w') as f:
                f.write(reverse_zone_definition)

        # tsig.key
        stdout, stderr = subprocess.Popen(
            ['tsig-keygen', self.config.client_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        ).communicate()
        tsig_key = stdout.decode('ascii')
        with open(tsig_key_file, 'w') as f:
            f.write(tsig_key)
        tsig_key = re.search(tsig_key_pattern, tsig_key).group(1)

        init_file.touch()
        return tsig_key

    def add(self, record: DNSRecord):
        self._add(record)

        arpa_record = self._arpa_record(record)
        if arpa_record:
            self._add(arpa_record)

    def remove(self, zone, record_name):
        LOG.info('removing record: %s, from zone: %s', record_name, zone)
        update = dns.update.Update(zone, keyring=self.keyring)
        update.delete(record_name)
        dns.query.tcp(update, self.current_ip, timeout=2)

    def list_docker_records(self, zone_name):
        zone = dns.zone.from_xfr(dns.query.xfr(self.current_ip, zone_name))
        managed_records = []
        docker_record = f'{self.config.client_name},{docker_source_id}'
        for name, node in zone.nodes.items():
            for rdataset in node.rdatasets:
                if rdataset.rdtype == dns.rdatatype.TXT:
                    values = {s.decode() for rdata in rdataset for s in rdata.strings}
                    if docker_record in values:
                        managed_records.append(str(name))
        return managed_records

    def _add(self, record: DNSRecord):
        LOG.info('Adding record: %s', record)
        update = dns.update.Update(record.zone, keyring=self.keyring)
        update.add(record.name, record.ttl, record.record_type, record.value)
        update.add(record.name, record.ttl, "TXT", f'{self.config.client_name},{record.source}')
        dns.query.tcp(update, self.current_ip, timeout=2)

    def _arpa_record(self, record: DNSRecord):
        if not self.config.reverse_zone:
            return

        if record.record_type != 'A':
            return

        ip_reverse = '.'.join(reversed(record.value.split('.')))
        reverse_zone_ip_section = self.config.reverse_zone.removesuffix('.in-addr.arpa')
        ip_reverse_prefix = ip_reverse.removesuffix(f'.{reverse_zone_ip_section}')

        if ip_reverse == ip_reverse_prefix:
            LOG.debug("IP doesn't belong to ARPA zone")
            return None

        return DNSRecord(self.config.reverse_zone, ip_reverse_prefix, 'PTR', f'{record.name}.{record.zone}.', ttl=record.ttl, source=record.source)
