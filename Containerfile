# BCM Agent for OpenShift
# Kubernetes integration wrapper for NVIDIA cm-lite-daemon
#
# IMPORTANT: This container requires NVIDIA's proprietary cm-lite-daemon
# which must be provided at build time from your BCM installation.

FROM quay.io/centos/centos:stream9
#FROM registry.access.redhat.com/ubi9/ubi:9.6

ARG VERSION=1.0.0

LABEL name="BCM Agent for Kubernetes"
LABEL vendor="Fabien Dupont"
LABEL maintainer="Fabien Dupont <fdupont@redhat.com>"
LABEL version="${VERSION}"
LABEL summary="Kubernetes Integration for NVIDIA BCM using cm-lite-daemon"
LABEL description="Kubernetes/OpenShift integration wrapper for NVIDIA Base Command Manager (BCM) using NVIDIA's cm-lite-daemon for hardware monitoring and node labeling"

# Install system utilities required by cm-lite-daemon
RUN dnf install -y \
    python3 \
    python3-pip \
    dmidecode \
    pciutils \
    ipmitool \
    hostname \
    unzip \
    && dnf clean all

# Create application directory structure
RUN mkdir -p /opt/bcm-agent \
             /etc/bcm-agent/certs \
             /var/log/bcm-agent \
             /var/run/bcm-agent

# Copy and extract NVIDIA cm-lite-daemon from build context
# This file must be copied from BCM installation: /cm/shared/apps/cm-lite-daemon-dist/cm-lite-daemon.zip
COPY cm-lite-daemon.zip /tmp/cm-lite-daemon.zip
RUN unzip /tmp/cm-lite-daemon.zip -d /opt/bcm-agent/ && \
    rm /tmp/cm-lite-daemon.zip && \
    chmod +x /opt/bcm-agent/cm-lite-daemon/cm-lite-daemon

# Install cm-lite-daemon Python dependencies from its requirements.txt
RUN pip3 install --no-cache-dir -r /opt/bcm-agent/cm-lite-daemon/requirements.txt

# Install additional dependencies for Kubernetes integration
RUN pip3 install --no-cache-dir \
    kubernetes \
    prometheus-client

# Create minimal config file to prevent fatal error on missing config
RUN echo '{}' > /opt/bcm-agent/cm-lite-daemon/etc/config.json

# Copy Kubernetes integration and entrypoint
COPY src/ /opt/bcm-agent/
RUN chmod +x /opt/bcm-agent/entrypoint.sh

# Set Python path to include cm-lite-daemon
ENV PYTHONPATH=/opt/bcm-agent/cm-lite-daemon:$PYTHONPATH

# Set working directory
WORKDIR /opt/bcm-agent

# OpenShift compatibility: Allow running as arbitrary UID
# Note: cm-lite-daemon needs privileged access for hardware monitoring
RUN chmod -R g+rwX /opt/bcm-agent /etc/bcm-agent /var/log/bcm-agent /var/run/bcm-agent && \
    chgrp -R 0 /opt/bcm-agent /etc/bcm-agent /var/log/bcm-agent /var/run/bcm-agent

# Expose Prometheus metrics port
EXPOSE 9100

# Health check - verify cm-lite-daemon is running
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD test -f /var/run/bcm-agent/cm-lite-daemon.pid && kill -0 $(cat /var/run/bcm-agent/cm-lite-daemon.pid)

# Run the entrypoint script
ENTRYPOINT ["/opt/bcm-agent/entrypoint.sh"]
