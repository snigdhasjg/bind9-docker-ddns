import logging
import os

from dotenv import dotenv_values, find_dotenv

LOG = logging.getLogger(__name__)


class Config:
    def __init__(self):
        envs = {
            **dotenv_values(find_dotenv("../.env.example")), # usecwd=True
            **os.environ
        }
        self.bind_home = envs.get('bind_home', '/etc/bind')
        self.trusted_cidrs = envs['trusted_cidrs'].split(',')
        self.dns_forwarders = envs['dns_forwarders'].split(',')
        self.zone = envs["zone"]
        self.reverse_zone = envs.get("reverse_zone")
        self.nameserver_hostname = envs["nameserver_hostname"]
        self.nameserver_email = envs["nameserver_email"]
        self.client_name = "bind9_docker_ddns"

        self.container_hostname_label = "com.snigji.bind9-docker-ddns.hostname"
        self.container_record_type_label = "com.snigji.bind9-docker-ddns.record-type"
        self.container_value_label = "com.snigji.bind9-docker-ddns.value"
        self.container_network_label = "com.snigji.bind9-docker-ddns.network"
