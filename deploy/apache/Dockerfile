# The official Apache image plus the openssl command, which entrypoint.sh uses to make the
# self-signed certificates on first start.
FROM httpd:2.4
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssl \
 && rm -rf /var/lib/apt/lists/*
