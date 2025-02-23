import logging
import os
import yaml

from dotenv import dotenv_values, find_dotenv

from bind9_docker_ddns.dns_record import DNSRecord, static_source_id

LOG = logging.getLogger(__name__)


class Config:
    def __init__(self):
        envs = {
            **dotenv_values(find_dotenv(usecwd=True)),
            **os.environ
        }
        self.bind_home = envs.get('bind_home', '/etc/bind')
        self.trusted_cidrs = envs['trusted_cidrs'].split(',')
        self.dns_forwarders = envs['dns_forwarders'].split(',')
        self.zone = envs["zone"]
        self.reverse_zone = envs.get("reverse_zone")
        self.nameserver_hostname = envs["nameserver_hostname"]
        self.client_name = "bind9-docker-ddns"

        static_records = yaml.safe_load(envs.get("static_records"))
        self.static_dns_records = []
        for zone_name, records in static_records.items():
            for hostname, value in records.items():
                record = value.split(',')
                self.static_dns_records.append(DNSRecord(zone_name, hostname, record[0], record[1], source=static_source_id))
