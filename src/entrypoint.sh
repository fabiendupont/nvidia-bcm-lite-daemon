#!/bin/bash
# SPDX-FileCopyrightText: Copyright 2025 Fabien Dupont <fdupont@redhat.com>
# SPDX-License-Identifier: Apache-2.0
#
# Entrypoint script for BCM Agent container
# Runs both cm-lite-daemon and Kubernetes node labeler

set -e

# Configuration from environment variables
BCM_HOST="${BCM_HOST:-master}"
BCM_PORT="${BCM_PORT:-8081}"
CERT_FILE="${CERT_FILE:-/etc/bcm-agent/certs/cert.pem}"
KEY_FILE="${KEY_FILE:-/etc/bcm-agent/certs/cert.key}"
CA_FILE="${CA_FILE:-/etc/bcm-agent/certs/cacert.pem}"
CONFIG_FILE="${CONFIG_FILE:-/etc/bcm-agent/config.json}"
PID_FILE="/var/run/bcm-agent/cm-lite-daemon.pid"
LOG_FILE="${LOG_FILE:-/var/log/bcm-agent/cm-lite-daemon.log}"

# Node name (should be set by DaemonSet via downward API)
NODE_NAME="${NODE_NAME:-$(hostname)}"

echo "========================================="
echo "BCM Agent for OpenShift"
echo "========================================="
echo "Node: $NODE_NAME"
echo "BCM Host: $BCM_HOST:$BCM_PORT"
echo "Config: $CONFIG_FILE"
echo "========================================="

# Ensure directories exist
mkdir -p /var/run/bcm-agent /var/log/bcm-agent

# Bootstrap certificate support for Kubernetes auto-provisioning
# If bootstrap certs are provided, use them to generate per-node certificates
BOOTSTRAP_CERT_DIR="/etc/bcm-bootstrap"
NODE_CERT_DIR="/var/lib/bcm-agent/certs"

if [ -f "$BOOTSTRAP_CERT_DIR/cert.pem" ] && [ -f "$BOOTSTRAP_CERT_DIR/cert.key" ]; then
    echo "Bootstrap certificates detected"

    # Ensure output directory exists
    mkdir -p "$NODE_CERT_DIR"

    # Check if per-node certificates already exist
    if [ ! -f "$NODE_CERT_DIR/cert.pem" ] || [ ! -f "$NODE_CERT_DIR/cert.key" ]; then
        echo "Generating per-node certificate for: $NODE_NAME"

        # Use register_node to generate per-node certificate
        cd /opt/bcm-agent/cm-lite-daemon
        if ./register_node \
            --host "$BCM_HOST" \
            --port "$BCM_PORT" \
            --node "$NODE_NAME" \
            --bootstrap-cert "$BOOTSTRAP_CERT_DIR/cert.pem" \
            --bootstrap-key "$BOOTSTRAP_CERT_DIR/cert.key" \
            --ca "$BOOTSTRAP_CERT_DIR/cacert.pem" \
            --cert "$NODE_CERT_DIR/cert.pem" \
            --key "$NODE_CERT_DIR/cert.key" \
            --disable-hostname-check \
            --no-service \
            --no-device-update \
            ${DEBUG:+--debug}; then
            echo "✓ Per-node certificate generated successfully"
        else
            echo "ERROR: Failed to generate per-node certificate"
            exit 1
        fi
    else
        echo "Per-node certificate already exists (idempotent)"
    fi

    # Always ensure CA certificate is present (in case it was missing)
    if [ ! -f "$NODE_CERT_DIR/cacert.pem" ]; then
        echo "Copying CA certificate to node cert directory"
        cp "$BOOTSTRAP_CERT_DIR/cacert.pem" "$NODE_CERT_DIR/cacert.pem"
    fi

    # Use per-node certificates for cm-lite-daemon
    CERT_FILE="$NODE_CERT_DIR/cert.pem"
    KEY_FILE="$NODE_CERT_DIR/cert.key"
    CA_FILE="$NODE_CERT_DIR/cacert.pem"

    echo "Using per-node certificates from: $NODE_CERT_DIR"
fi

# Check for certificates
if [ ! -f "$CERT_FILE" ]; then
    echo "WARNING: Certificate file not found: $CERT_FILE"
    echo "cm-lite-daemon may fail to start without proper certificates"
fi

if [ ! -f "$CA_FILE" ]; then
    echo "WARNING: CA certificate file not found: $CA_FILE"
fi

# Function to handle shutdown
shutdown() {
    echo "Shutting down BCM Agent..."

    # Stop cm-lite-daemon
    if [ -f "$PID_FILE" ]; then
        CM_PID=$(cat "$PID_FILE")
        if kill -0 "$CM_PID" 2>/dev/null; then
            echo "Stopping cm-lite-daemon (PID: $CM_PID)..."
            kill -TERM "$CM_PID"
            # Wait up to 30 seconds for graceful shutdown
            for _ in {1..30}; do
                if ! kill -0 "$CM_PID" 2>/dev/null; then
                    break
                fi
                sleep 1
            done
            # Force kill if still running
            if kill -0 "$CM_PID" 2>/dev/null; then
                echo "Force killing cm-lite-daemon..."
                kill -9 "$CM_PID"
            fi
        fi
    fi

    # Stop K8s labeler
    if [ -n "$K8S_PID" ] && kill -0 "$K8S_PID" 2>/dev/null; then
        echo "Stopping K8s node labeler (PID: $K8S_PID)..."
        kill -TERM "$K8S_PID"
        wait "$K8S_PID" 2>/dev/null || true
    fi

    echo "Shutdown complete"
    exit 0
}

# Set up signal handlers
trap shutdown SIGTERM SIGINT

# Change to cm-lite-daemon directory
cd /opt/bcm-agent/cm-lite-daemon

# Build cm-lite-daemon arguments as array
CM_ARGS=()

# Add host/port if not using config file
if [ ! -f "$CONFIG_FILE" ]; then
    CM_ARGS+=(--host "$BCM_HOST" --port "$BCM_PORT")
fi

# Add certificate files
if [ -f "$CERT_FILE" ]; then
    CM_ARGS+=(--cert "$CERT_FILE" --key "$KEY_FILE")
fi

if [ -f "$CA_FILE" ]; then
    CM_ARGS+=(--ca "$CA_FILE")
fi

# Add config file if it exists
if [ -f "$CONFIG_FILE" ]; then
    CM_ARGS+=(--config "$CONFIG_FILE")
fi

# Add node name
CM_ARGS+=(--node "$NODE_NAME")

# Disable hostname check (certificate may not match hostname)
CM_ARGS+=(--disable-hostname-check)

# Enable debug if requested
if [ "$DEBUG" = "true" ]; then
    CM_ARGS+=(--debug)
fi

# Run cm-lite-daemon in foreground (no --daemon flag for container)
# Container runtime will manage the process lifecycle
echo "Starting cm-lite-daemon..."

# Check if running in Kubernetes (K8s sets KUBERNETES_SERVICE_HOST)
if [ -n "$KUBERNETES_SERVICE_HOST" ] && [ "$DISABLE_LABELING" != "true" ]; then
    echo "Kubernetes environment detected - starting with node labeler"

    # Check if running in metrics-only mode (skip cm-lite-daemon)
    if [ "$METRICS_ONLY" = "true" ]; then
        echo "METRICS_ONLY mode - skipping cm-lite-daemon"
        echo "Starting Kubernetes node labeler..."
        cd /opt/bcm-agent
        exec python3 k8s_node_labeler.py \
            --interval "${SYNC_INTERVAL:-300}" \
            --label-prefix "${LABEL_PREFIX:-bcm.nvidia.com}" \
            --metrics-port "${METRICS_PORT:-9100}" \
            --metrics-only \
            ${DEBUG:+--debug}
    fi

    # Start cm-lite-daemon in background
    ./cm-lite-daemon "${CM_ARGS[@]}" &
    CM_DAEMON_PID=$!
    echo "cm-lite-daemon started (PID: $CM_DAEMON_PID)"

    # Start K8s node labeler in background
    echo "Starting Kubernetes node labeler..."
    cd /opt/bcm-agent
    python3 k8s_node_labeler.py \
        --interval "${SYNC_INTERVAL:-300}" \
        --label-prefix "${LABEL_PREFIX:-bcm.nvidia.com}" \
        --metrics-port "${METRICS_PORT:-9100}" \
        ${DEBUG:+--debug} \
        &
    K8S_PID=$!
    echo "K8s node labeler started (PID: $K8S_PID)"

    # Wait for either process to exit
    while true; do
        # Check cm-lite-daemon
        if ! kill -0 "$CM_DAEMON_PID" 2>/dev/null; then
            echo "ERROR: cm-lite-daemon died unexpectedly"
            kill -TERM "$K8S_PID" 2>/dev/null
            exit 1
        fi

        # Check K8s labeler
        if ! kill -0 "$K8S_PID" 2>/dev/null; then
            echo "ERROR: K8s node labeler died unexpectedly"
            kill -TERM "$CM_DAEMON_PID" 2>/dev/null
            exit 1
        fi

        sleep 10
    done
else
    # Non-Kubernetes environment (RHEL/Quadlet) - run cm-lite-daemon only
    echo "Running in standalone mode (cm-lite-daemon only)"
    exec ./cm-lite-daemon "${CM_ARGS[@]}"
fi
