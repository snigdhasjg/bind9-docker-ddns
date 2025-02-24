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
from bind9_docker_ddns.dns_record import DNSRecord
from bind9_docker_ddns.dns_record import docker_source_id
from bind9_docker_ddns.dns_record import static_source_id
from bind9_docker_ddns.dns_record import value_types


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
            with open(init_file, 'r') as f:
                configured_ip = f.read()
                if configured_ip != self.current_ip:
                    LOG.error("IP changed, either use %s or clean all volume and restart the server", configured_ip)
                    raise Exception("IP changed, please clean all volume and restart the server")
            # tsig.key
            with open(tsig_key_file, 'r') as f:
                tsig_key = f.read()
                return re.search(tsig_key_pattern, tsig_key).group(1)

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

        with open(init_file, 'w') as f:
            f.write(self.current_ip)
        return tsig_key

    def list(self, zone_name):
        zone = dns.zone.from_xfr(dns.query.xfr(self.current_ip, zone_name))
        managed_records = dict()
        docker_record_id = f'{self.config.client_name},{docker_source_id}'
        static_record_id = f'{self.config.client_name},{static_source_id}'

        for name, node in zone.nodes.items():
            is_managed_record = False
            managed_record_values = []
            for rdataset in node.rdatasets:
                if rdataset.rdtype == dns.rdatatype.TXT:
                    values = [r.decode() for rdata in rdataset for r in rdata.strings]
                    if docker_record_id in values or static_record_id in values:
                        is_managed_record = True
                    continue

                record_type = dns.rdatatype.to_text(rdataset.rdtype)
                if record_type in value_types:
                    for r in rdataset:
                        value = r.to_text()
                        managed_record_values.append(DNSRecord(zone_name, str(name), record_type, value))

            if is_managed_record:
                managed_records[str(name)] = managed_record_values

        return managed_records

    def add(self, record: DNSRecord):
        LOG.info('Adding record: %s', record)
        update = dns.update.Update(record.zone, keyring=self.keyring)
        update.add(record.name, record.ttl, record.record_type, record.value)
        owner_record = record.owner_record(f'{self.config.client_name},{record.source}')
        update.add(owner_record.name, owner_record.ttl, owner_record.record_type, owner_record.value)
        dns.query.tcp(update, self.current_ip, timeout=2)

    def remove(self, zone, record_name):
        LOG.info('removing record: %s, from zone: %s', record_name, zone)
        update = dns.update.Update(zone, keyring=self.keyring)
        update.delete(record_name)
        dns.query.tcp(update, self.current_ip, timeout=2)
