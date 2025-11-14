# BCM Agent for OpenShift
# Based on NVIDIA cm-lite-daemon with Kubernetes integration

FROM quay.io/centos/centos:stream9
#FROM registry.access.redhat.com/ubi9/ubi:9.6

ARG VERSION=1.0.0

LABEL name="NVIDIA BCM Agent for OpenShift"
LABEL vendor="NVIDIA"
LABEL version="${VERSION}"
LABEL summary="BCM Lite Daemon with Kubernetes Integration"
LABEL description="Integrates NVIDIA Base Command Manager with OpenShift using cm-lite-daemon for hardware monitoring and node labeling"

# Install system utilities required by cm-lite-daemon
RUN dnf install -y \
    python3 \
    python3-pip \
    dmidecode \
    pciutils \
    ipmitool \
    hostname \
    && dnf clean all

# Install cm-lite-daemon Python dependencies from its requirements.txt
COPY cm-lite-daemon/requirements.txt /tmp/cm-lite-requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/cm-lite-requirements.txt

# Install additional dependencies for Kubernetes integration
RUN pip3 install --no-cache-dir \
    kubernetes \
    prometheus-client

# Create application directory structure
RUN mkdir -p /opt/bcm-agent/cm-lite-daemon \
             /etc/bcm-agent/certs \
             /var/log/bcm-agent \
             /var/run/bcm-agent

# Copy cm-lite-daemon
COPY cm-lite-daemon/ /opt/bcm-agent/cm-lite-daemon/
RUN chmod +x /opt/bcm-agent/cm-lite-daemon/cm-lite-daemon

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
