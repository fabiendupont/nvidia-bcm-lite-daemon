# Bootstrap Certificate Setup Guide

This guide explains how to set up bootstrap certificates for automatic per-node certificate provisioning in Kubernetes/OpenShift deployments.

## Overview

The bcm-agent uses a **bootstrap certificate pattern** for secure, scalable certificate management:

1. **Bootstrap Certificate** - A shared certificate with limited permissions, used only for requesting new certificates
2. **Per-Node Certificates** - Unique certificates automatically generated for each node on first startup
3. **Persistent Storage** - Certificates stored on hostPath and reused across pod restarts

### Why Bootstrap Certificates?

**Security Benefits:**
- Each node gets a unique certificate (CN=hostname)
- Private keys never leave the node
- Bootstrap cert has minimal permissions (only certificate requests)
- Scales to unlimited nodes (no Kubernetes Secret size limits)

**Operational Benefits:**
- Fully automatic - no manual certificate management
- Idempotent - certificates reused across pod restarts
- Simple deployment - single Secret shared by all pods
- No per-node configuration required

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ Kubernetes Secret (bcm-bootstrap-cert)                       │
│  - cacert.pem  (BCM CA certificate)                          │
│  - cert.pem    (Bootstrap certificate - shared)              │
│  - cert.key    (Bootstrap private key - shared)              │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ Mounted to all pods as /etc/bcm-bootstrap
                 ↓
┌────────────────────────────────────────────────────────────────┐
│ BCM Agent Pod (per node)                                       │
│                                                                 │
│  1. Detects bootstrap certificates in /etc/bcm-bootstrap       │
│  2. Checks if per-node cert exists in /var/lib/bcm-agent/certs │
│  3. If not, runs: register_node --bootstrap-cert ...           │
│  4. Per-node cert generated with CN=<nodename>                 │
│  5. Certificate persisted on hostPath (survives pod restart)   │
│  6. cm-lite-daemon uses per-node certificate                   │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

## Step 1: Create Bootstrap Certificate on BCM

Bootstrap certificates should have minimal permissions - only the ability to request new certificates.

### Option 1: Using pythoncm (Recommended)

```bash
# On BCM head node
cat > /tmp/create_bootstrap_cert.py << 'EOF'
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/cm/local/apps/cmd/pythoncm/lib/python3.12/site-packages')

from pythoncm.cluster import Cluster
from pythoncm.settings import Settings
from pythoncm.entity import Certificate

# Connect to BCM
settings = Settings(
    host="localhost",
    port=8081,
    cert_file="/cm/local/apps/cmd/etc/cert.pem",
    key_file="/cm/local/apps/cmd/etc/cert.key"
)

cluster = Cluster(settings)

# Create bootstrap certificate
print("Creating bootstrap certificate...")
cert = Certificate(cluster)
cert.commonName = "k8s-bootstrap"
cert.profile = "bootstrap"  # Limited permissions profile
cert.bits = 4096
cert.validityDays = 365

# Create the certificate
result = cert.create()
print(f"Certificate created with serial number: {result['serial']}")
print(f"UUID: {result['uuid']}")

# Save certificate files
output_dir = "/tmp/bootstrap-cert"
cert.save(output_dir + "/cert.pem", output_dir + "/cert.key")
print(f"\nCertificate saved to: {output_dir}/")
print(f"  - {output_dir}/cert.pem")
print(f"  - {output_dir}/cert.key")
print(f"\nCopy CA certificate:")
print(f"  cp /cm/local/apps/cmd/etc/cacert.pem {output_dir}/")
EOF

chmod +x /tmp/create_bootstrap_cert.py
python3 /tmp/create_bootstrap_cert.py
```

### Option 2: Using register_node

```bash
# On BCM head node
mkdir -p /tmp/bootstrap-cert

cd /cm/local/apps/cm-lite-daemon
./register_node \
  --host localhost \
  --port 8081 \
  --node k8s-bootstrap \
  --bootstrap-cert /cm/local/apps/cmd/etc/cert.pem \
  --bootstrap-key /cm/local/apps/cmd/etc/cert.key \
  --ca /cm/local/apps/cmd/etc/cacert.pem \
  --cert /tmp/bootstrap-cert/cert.pem \
  --key /tmp/bootstrap-cert/cert.key \
  --no-service \
  --no-device-update

# Copy CA certificate
cp /cm/local/apps/cmd/etc/cacert.pem /tmp/bootstrap-cert/
```

### Option 3: Using cmsh (Manual)

```bash
# On BCM head node
cmsh -c "cert; create k8s-bootstrap; set profile bootstrap; set bits 4096; set validitydays 365; commit"

# Export certificate (requires finding serial number)
# Note: cmsh doesn't provide direct certificate export
# Use pythoncm method instead for easier certificate retrieval
```

## Step 2: Verify Bootstrap Certificate

```bash
# Check certificate details
openssl x509 -in /tmp/bootstrap-cert/cert.pem -noout -subject -dates

# Expected output:
# subject=C=US, ST=California, L=Santa Clara, O=NVIDIA Inc, OU=Bright Licensing, CN=k8s-bootstrap
# notBefore=Nov 10 17:00:00 2025 GMT
# notAfter=Nov 10 17:00:00 2026 GMT

# Verify certificate chain
openssl verify -CAfile /tmp/bootstrap-cert/cacert.pem /tmp/bootstrap-cert/cert.pem

# Expected output:
# /tmp/bootstrap-cert/cert.pem: OK
```

## Step 3: Create Kubernetes Secret

### From BCM Head Node

If your Kubernetes cluster is accessible from the BCM head node:

```bash
# Copy certificates to bootstrap directory
export CERT_DIR="/tmp/bootstrap-cert"

# Create Secret in Kubernetes
kubectl create secret generic bcm-bootstrap-cert \
  --from-file=cacert.pem=$CERT_DIR/cacert.pem \
  --from-file=cert.pem=$CERT_DIR/cert.pem \
  --from-file=cert.key=$CERT_DIR/cert.key \
  --namespace default \
  --dry-run=client -o yaml | kubectl apply -f -
```

### From Remote Machine

If you need to transfer certificates to another machine:

```bash
# On BCM head node - create tarball
cd /tmp/bootstrap-cert
tar czf bootstrap-cert.tar.gz cacert.pem cert.pem cert.key

# Transfer to machine with kubectl access
scp bootstrap-cert.tar.gz admin@k8s-master:/tmp/

# On Kubernetes master
cd /tmp
tar xzf bootstrap-cert.tar.gz

# Create Secret
kubectl create secret generic bcm-bootstrap-cert \
  --from-file=cacert.pem=/tmp/cacert.pem \
  --from-file=cert.pem=/tmp/cert.pem \
  --from-file=cert.key=/tmp/cert.key \
  --namespace default

# Clean up sensitive files
rm -f /tmp/cacert.pem /tmp/cert.pem /tmp/cert.key /tmp/bootstrap-cert.tar.gz
```

### Using Helper Script

The bcm-agent repository includes a helper script:

```bash
cd /root/bcm/bcm-agent

# Create Secret from directory
./scripts/create-bootstrap-secret.sh /tmp/bootstrap-cert default

# Or specify custom Secret name
./scripts/create-bootstrap-secret.sh /tmp/bootstrap-cert default my-bootstrap-cert
```

## Step 4: Verify Secret

```bash
# Check Secret exists
kubectl get secret bcm-bootstrap-cert -n default

# Verify Secret contains all three files
kubectl describe secret bcm-bootstrap-cert -n default

# Expected output:
# Name:         bcm-bootstrap-cert
# Namespace:    default
# Type:         Opaque
# Data
# ====
# cacert.pem:  4356 bytes
# cert.key:    1704 bytes
# cert.pem:    1338 bytes

# Verify certificate content (base64 encoded)
kubectl get secret bcm-bootstrap-cert -n default -o jsonpath='{.data.cert\.pem}' | base64 -d | openssl x509 -noout -subject

# Expected output:
# subject=C=US, ST=California, L=Santa Clara, O=NVIDIA Inc, OU=Bright Licensing, CN=k8s-bootstrap
```

## Step 5: Deploy with Helm

```bash
# Deploy bcm-agent with bootstrap certificate
helm install bcm-agent ./helm/bcm-agent \
  --namespace default \
  --set image.tag=1.0.2 \
  --set config.bcm.host=10.141.255.254 \
  --set certificates.secretName=bcm-bootstrap-cert
```

## Step 6: Verify Per-Node Certificate Generation

```bash
# Watch pod logs during startup
kubectl logs -f <bcm-agent-pod-name>

# Expected output:
# =========================================
# BCM Agent for OpenShift
# =========================================
# Node: node001
# BCM Host: 10.141.255.254:8081
# =========================================
# Bootstrap certificates detected
# Generating per-node certificate for: node001
# INFO     Certificate requested: 5183b647-33ed-470a-9665-73b6b801244c, waiting for it to be issued...
# INFO     Certificate issued successfully
# ✓ Per-node certificate generated successfully
# Using per-node certificates from: /var/lib/bcm-agent/certs
# Starting cm-lite-daemon...
# INFO     Websocket connected
# INFO     CMDaemon started

# Verify per-node certificate on host
kubectl get pod <bcm-agent-pod-name> -o jsonpath='{.spec.nodeName}'
# Note the node name, then SSH to that node

# On the Kubernetes node
ls -la /var/lib/bcm-agent/certs/

# Expected output:
# total 16
# drwxr-xr-x. 2 root root   56 Nov 10 18:11 .
# drwxr-xr-x. 3 root root   19 Nov 10 18:04 ..
# -r--------. 1 root root 4356 Nov 10 18:11 cacert.pem
# -rw-------. 1 root root 1704 Nov 10 18:05 cert.key
# -rw-------. 1 root root 1338 Nov 10 18:05 cert.pem

# Check certificate CN matches node name
openssl x509 -in /var/lib/bcm-agent/certs/cert.pem -noout -subject

# Expected output (for node001):
# subject=C=US, ST=California, L=Santa Clara, O=NVIDIA Inc, OU=Bright Licensing, CN=node001
```

## Certificate Lifecycle

### Initial Deployment

1. Bootstrap Secret created (one-time setup)
2. Helm deploys DaemonSet with bootstrap certificates
3. Each pod detects bootstrap certs and generates per-node certificate
4. Certificates persisted on hostPath `/var/lib/bcm-agent/certs/`
5. cm-lite-daemon connects using per-node certificate

### Pod Restart (Idempotent)

1. Pod restarts (crash, upgrade, node drain)
2. Pod detects bootstrap certs in `/etc/bcm-bootstrap`
3. Pod checks if per-node cert exists in `/var/lib/bcm-agent/certs/`
4. **Certificate already exists** - skips generation
5. Ensures CA cert is present (copies if missing)
6. cm-lite-daemon uses existing per-node certificate

### New Node Added to Cluster

1. DaemonSet schedules pod on new node
2. Pod starts with bootstrap certificates
3. No per-node cert exists on new node
4. Automatically generates new certificate with CN=<new-node-name>
5. Certificate persisted and used by cm-lite-daemon

### Certificate Rotation

To rotate certificates (e.g., before expiry):

```bash
# Option 1: Delete per-node certificates on node (will regenerate on next pod start)
# SSH to node
rm -rf /var/lib/bcm-agent/certs/*

# Restart pod on that node
kubectl delete pod <pod-name>
# New pod will regenerate certificate

# Option 2: Revoke and regenerate (future enhancement)
# Use pythoncm to revoke old certificate
# Delete local cert files
# Restart pod to regenerate
```

## Troubleshooting

### Bootstrap Secret Not Found

```bash
# Error: Secret "bcm-bootstrap-cert" not found

# Verify Secret exists in correct namespace
kubectl get secret bcm-bootstrap-cert -n default

# If missing, recreate Secret (see Step 3)
```

### Certificate Generation Fails

```bash
# Check pod logs
kubectl logs <pod-name> | grep -A10 "Generating per-node certificate"

# Common issues:
# - Cannot connect to BCM host (check network, firewall)
# - Bootstrap certificate expired or invalid
# - Incorrect BCM host/port configuration
# - Certificate request denied by BCM (check permissions)

# Verify connectivity from pod
kubectl exec <pod-name> -- ping -c 3 10.141.255.254
kubectl exec <pod-name> -- timeout 5 bash -c '</dev/tcp/10.141.255.254/8081' && echo "Port open"
```

### Per-Node Certificate Not Persisting

```bash
# Check hostPath volume mount
kubectl describe pod <pod-name> | grep -A5 "node-certs"

# Verify directory exists on host
# SSH to node
ls -ld /var/lib/bcm-agent/certs

# Check permissions
ls -la /var/lib/bcm-agent/certs/

# If directory missing, pod should create it
# If permissions wrong, check pod securityContext
```

### CA Certificate Missing After Upgrade

```bash
# Symptom: SSL certificate verify failed
# Fixed in v1.0.2+ (always ensures CA cert is present)

# Manual fix if needed:
# SSH to node
cp /etc/bcm-bootstrap/cacert.pem /var/lib/bcm-agent/certs/cacert.pem

# Or delete pod to trigger fix
kubectl delete pod <pod-name>
```

### Multiple Certificates for Same Node

```bash
# Check certificates in BCM
# On BCM head node
cmsh -c "cert; list" | grep node001

# If duplicates exist, revoke old ones
# Option 1: Via cmsh
cmsh -c "cert; use <cert-name>; revoke; commit"

# Option 2: Via pythoncm (recommended)
# See Certificate Management section
```

## Security Considerations

### Bootstrap Certificate Permissions

The bootstrap certificate should have **minimal permissions**:
- ✅ Request new certificates (CN can be different from bootstrap CN)
- ❌ Read other certificates
- ❌ Revoke certificates
- ❌ Modify cluster configuration
- ❌ Access sensitive data

**Best Practice:** Create a dedicated certificate profile for bootstrap certificates with restricted permissions.

### Secret Access Control

```bash
# Limit who can read the bootstrap Secret
kubectl create rolebinding bcm-bootstrap-secret-reader \
  --role=secret-reader \
  --serviceaccount=default:bcm-agent \
  --namespace=default

# Prevent unauthorized access
kubectl create role secret-reader \
  --verb=get \
  --resource=secrets \
  --resource-name=bcm-bootstrap-cert
```

### Certificate Rotation Policy

**Recommendations:**
- Bootstrap certificate validity: 1-2 years
- Per-node certificate validity: 30-90 days (generated by BCM policy)
- Automate rotation before expiry
- Monitor certificate expiration dates

### Private Key Security

**Bootstrap Certificate:**
- Stored in Kubernetes Secret (encrypted at rest if etcd encryption enabled)
- Accessible to all bcm-agent pods
- Limited permissions reduce blast radius

**Per-Node Certificates:**
- Private keys stored only on individual nodes (never in Secrets)
- Private keys never leave the node
- File permissions: 0600 (root only)

## Advanced Configuration

### Custom Certificate Profile

Create a custom BCM certificate profile for bootstrap certificates:

```bash
# On BCM head node via cmsh
cmsh -c "cert; profile; create bootstrap-k8s; set validitydays 730; set permissions cert-request-only; commit"

# Update bootstrap certificate creation to use custom profile
# In create_bootstrap_cert.py:
cert.profile = "bootstrap-k8s"
```

### Multiple Kubernetes Clusters

Each Kubernetes cluster should have its own bootstrap certificate:

```bash
# Create separate bootstrap certificates
# Cluster 1
cert.commonName = "k8s-prod-bootstrap"

# Cluster 2
cert.commonName = "k8s-dev-bootstrap"

# This allows per-cluster access control and auditing
```

### Certificate Monitoring

Monitor certificate expiration dates:

```bash
# Check bootstrap certificate expiry
kubectl get secret bcm-bootstrap-cert -o jsonpath='{.data.cert\.pem}' | \
  base64 -d | \
  openssl x509 -noout -enddate

# Check per-node certificate expiry (on node)
openssl x509 -in /var/lib/bcm-agent/certs/cert.pem -noout -enddate

# Set up alerts for certificates expiring in < 30 days
```

## Summary

**Bootstrap certificate setup steps:**
1. ✅ Create bootstrap certificate on BCM with limited permissions
2. ✅ Verify certificate validity and permissions
3. ✅ Create Kubernetes Secret with bootstrap cert + CA
4. ✅ Deploy bcm-agent via Helm with `certificates.secretName`
5. ✅ Verify per-node certificates auto-generated on each node
6. ✅ Confirm cm-lite-daemon connects to BCM successfully

**Key benefits:**
- Automatic and idempotent
- Secure (unique per-node certs, private keys never shared)
- Scalable (no Secret size limits)
- Simple (one-time bootstrap setup)

For more information, see:
- [Helm Chart README](../helm/bcm-agent/README.md)
- [Kubernetes Deployment Guide](KUBERNETES_DEPLOYMENT.md)
- [Certificate Management](CERTIFICATE_MANAGEMENT.md)
