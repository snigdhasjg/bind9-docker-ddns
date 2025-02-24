FROM python:3.12-bookworm

# https://www.digitalocean.com/community/tutorials/how-to-configure-bind-as-a-private-network-dns-server-on-debian-9
# https://reintech.io/blog/installing-configuring-bind-dns-server-debian-12
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y bind9 dnsutils

WORKDIR /tmp/build

COPY pyproject.toml pyproject.toml
RUN pip install --no-cache-dir .

COPY . .
RUN pip install --no-cache-dir .

WORKDIR /etc/bind
RUN rm -rf /tmp/build

ENTRYPOINT ["bind9-docker-ddns"]