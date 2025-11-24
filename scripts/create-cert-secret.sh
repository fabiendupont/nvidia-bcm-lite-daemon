#!/bin/bash
# SPDX-FileCopyrightText: Copyright 2025 Fabien Dupont <fdupont@redhat.com>
# SPDX-License-Identifier: Apache-2.0
#
# Helper script to create Kubernetes Secret from BCM certificate files
#
# Usage:
#   ./scripts/create-cert-secret.sh [cert-directory] [namespace]
#
# Default cert directory: /cm/local/apps/cm-lite-daemon/etc
# Default namespace: bcm-agent

set -e

# Configuration
CERT_DIR="${1:-/cm/local/apps/cm-lite-daemon/etc}"
NAMESPACE="${2:-bcm-agent}"
SECRET_NAME="bcm-agent-certs"

# Certificate file names
CACERT_FILE="cacert.pem"
CERT_FILE="cert.pem"
KEY_FILE="cert.key"

echo "========================================="
echo "BCM Agent Certificate Secret Creator"
echo "========================================="
echo "Certificate directory: $CERT_DIR"
echo "Namespace: $NAMESPACE"
echo "Secret name: $SECRET_NAME"
echo ""

# Check if certificate directory exists
if [ ! -d "$CERT_DIR" ]; then
    echo "ERROR: Certificate directory not found: $CERT_DIR"
    exit 1
fi

# Check if certificate files exist
if [ ! -f "$CERT_DIR/$CACERT_FILE" ]; then
    echo "ERROR: CA certificate not found: $CERT_DIR/$CACERT_FILE"
    exit 1
fi

if [ ! -f "$CERT_DIR/$CERT_FILE" ]; then
    echo "ERROR: Client certificate not found: $CERT_DIR/$CERT_FILE"
    exit 1
fi

if [ ! -f "$CERT_DIR/$KEY_FILE" ]; then
    echo "ERROR: Private key not found: $CERT_DIR/$KEY_FILE"
    exit 1
fi

echo "Found all required certificate files:"
echo "  - $CACERT_FILE"
echo "  - $CERT_FILE"
echo "  - $KEY_FILE"
echo ""

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl not found in PATH"
    echo "Please install kubectl to create the Secret"
    exit 1
fi

# Check if namespace exists, create if not
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    echo "Namespace '$NAMESPACE' does not exist. Creating it..."
    kubectl create namespace "$NAMESPACE"
    echo "Namespace created."
    echo ""
fi

# Check if Secret already exists
if kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" &> /dev/null; then
    echo "WARNING: Secret '$SECRET_NAME' already exists in namespace '$NAMESPACE'"
    read -p "Do you want to delete and recreate it? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Deleting existing Secret..."
        kubectl delete secret "$SECRET_NAME" -n "$NAMESPACE"
    else
        echo "Aborted."
        exit 1
    fi
fi

# Create the Secret
echo "Creating Secret '$SECRET_NAME' in namespace '$NAMESPACE'..."
if kubectl create secret generic "$SECRET_NAME" \
    --from-file="$CACERT_FILE=$CERT_DIR/$CACERT_FILE" \
    --from-file="$CERT_FILE=$CERT_DIR/$CERT_FILE" \
    --from-file="$KEY_FILE=$CERT_DIR/$KEY_FILE" \
    --namespace="$NAMESPACE"; then
    echo ""
    echo "========================================="
    echo "SUCCESS!"
    echo "========================================="
    echo "Secret '$SECRET_NAME' created in namespace '$NAMESPACE'"
    echo ""
    echo "You can verify the Secret with:"
    echo "  kubectl get secret $SECRET_NAME -n $NAMESPACE"
    echo "  kubectl describe secret $SECRET_NAME -n $NAMESPACE"
    echo ""
    echo "To view the certificate data:"
    echo "  kubectl get secret $SECRET_NAME -n $NAMESPACE -o yaml"
else
    echo ""
    echo "ERROR: Failed to create Secret"
    exit 1
fi
