# Certificate Lifecycle Management

Complete guide for managing BCM certificates in Kubernetes environments, including creation, rotation, revocation, and monitoring.

## Table of Contents

- [Overview](#overview)
- [Certificate Types](#certificate-types)
- [Certificate Creation](#certificate-creation)
- [Certificate Monitoring](#certificate-monitoring)
- [Certificate Rotation](#certificate-rotation)
- [Certificate Revocation](#certificate-revocation)
- [Troubleshooting](#troubleshooting)
- [Automation](#automation)

## Overview

The bcm-agent uses a two-tier certificate system:

1. **Bootstrap Certificate** - Shared credential for requesting per-node certificates
2. **Per-Node Certificates** - Unique certificates for each Kubernetes node

### Certificate Hierarchy

```
BCM Certificate Authority (CA)
│
├─> Bootstrap Certificate (CN=k8s-bootstrap)
│   └─> Used by all pods to request per-node certificates
│
└─> Per-Node Certificates (CN=node001, CN=node002, ...)
    └─> Unique certificate per Kubernetes node
```

### Certificate Flow

```
Bootstrap Phase (one-time):
1. Admin creates bootstrap certificate on BCM
2. Admin creates Kubernetes Secret with bootstrap cert
3. Admin deploys bcm-agent Helm chart

Per-Node Provisioning (automatic):
1. Pod starts with bootstrap certificate
2. entrypoint.sh checks if per-node cert exists
3. If not, calls register_node with bootstrap cert
4. BCM issues per-node certificate (CN=nodename)
5. Certificate saved to hostPath /var/lib/bcm-agent/certs
6. cm-lite-daemon uses per-node certificate
7. Pod restarts reuse existing per-node certificate (idempotent)
```

## Certificate Types

### Bootstrap Certificate

**Purpose:** Request new certificates for Kubernetes nodes

**Properties:**
- **Common Name:** k8s-bootstrap (or cluster-specific name)
- **Profile:** bootstrap (limited permissions)
- **Validity:** 365-730 days (long-lived)
- **Storage:** Kubernetes Secret (shared across all pods)
- **Permissions:** Certificate request only

**Security Considerations:**
- Shared among all pods (necessary for auto-provisioning)
- Limited blast radius (can only request certificates)
- Should not have other BCM permissions
- Secret should be protected by Kubernetes RBAC

### Per-Node Certificates

**Purpose:** Authenticate individual nodes to BCM

**Properties:**
- **Common Name:** Node hostname (e.g., node001)
- **Profile:** node (full node permissions)
- **Validity:** 30-90 days (short-lived for security)
- **Storage:** hostPath on individual nodes (not in Secrets)
- **Permissions:** Full node operations (monitoring, status updates)

**Security Considerations:**
- Private keys never leave the node
- Unique per node (compromise of one doesn't affect others)
- Shorter validity period (rotate more frequently)
- Stored on node filesystem with strict permissions (0600)

## Certificate Creation

### Creating Bootstrap Certificate

**Method 1: Using pythoncm (Recommended)**

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
cert = Certificate(cluster)
cert.commonName = "k8s-prod-bootstrap"  # Use cluster-specific name
cert.profile = "bootstrap"
cert.bits = 4096
cert.validityDays = 730  # 2 years

# Generate certificate
result = cert.create()
print(f"✓ Bootstrap certificate created")
print(f"  Serial: {result['serial']}")
print(f"  UUID: {result['uuid']}")
print(f"  Valid for: {cert.validityDays} days")

# Save to files
import os
os.makedirs("/tmp/k8s-bootstrap-cert", exist_ok=True)
cert.save(
    cert_file="/tmp/k8s-bootstrap-cert/cert.pem",
    key_file="/tmp/k8s-bootstrap-cert/cert.key"
)

# Copy CA certificate
import shutil
shutil.copy(
    "/cm/local/apps/cmd/etc/cacert.pem",
    "/tmp/k8s-bootstrap-cert/cacert.pem"
)

print(f"\n✓ Certificate files saved to: /tmp/k8s-bootstrap-cert/")
print(f"  - cacert.pem (CA)")
print(f"  - cert.pem (certificate)")
print(f"  - cert.key (private key)")
EOF

chmod +x /tmp/create_bootstrap_cert.py
python3 /tmp/create_bootstrap_cert.py
```

**Method 2: Using register_node**

```bash
# On BCM head node
mkdir -p /tmp/k8s-bootstrap-cert

cd /cm/local/apps/cm-lite-daemon
./register_node \
  --host localhost \
  --port 8081 \
  --node k8s-prod-bootstrap \
  --bootstrap-cert /cm/local/apps/cmd/etc/cert.pem \
  --bootstrap-key /cm/local/apps/cmd/etc/cert.key \
  --ca /cm/local/apps/cmd/etc/cacert.pem \
  --cert /tmp/k8s-bootstrap-cert/cert.pem \
  --key /tmp/k8s-bootstrap-cert/cert.key \
  --no-service \
  --no-device-update

# Copy CA
cp /cm/local/apps/cmd/etc/cacert.pem /tmp/k8s-bootstrap-cert/
```

### Creating Per-Node Certificates

Per-node certificates are created **automatically** by the entrypoint.sh script.

**Manual creation (for testing):**

```bash
# On BCM head node or from a system with bootstrap certificate
cd /cm/local/apps/cm-lite-daemon

./register_node \
  --host 10.141.255.254 \
  --port 8081 \
  --node node001 \
  --bootstrap-cert /tmp/k8s-bootstrap-cert/cert.pem \
  --bootstrap-key /tmp/k8s-bootstrap-cert/cert.key \
  --ca /tmp/k8s-bootstrap-cert/cacert.pem \
  --cert /tmp/node001-cert.pem \
  --key /tmp/node001-key.pem \
  --disable-hostname-check \
  --no-service \
  --no-device-update
```

## Certificate Monitoring

### Checking Certificate Expiration

**Bootstrap certificate (from Secret):**

```bash
# Get expiration date
kubectl get secret bcm-bootstrap-cert -n default \
  -o jsonpath='{.data.cert\.pem}' | \
  base64 -d | \
  openssl x509 -noout -enddate

# Get days until expiration
kubectl get secret bcm-bootstrap-cert -n default \
  -o jsonpath='{.data.cert\.pem}' | \
  base64 -d | \
  openssl x509 -noout -checkend 2592000  # 30 days
# Exit code 0 = valid for > 30 days
# Exit code 1 = expires within 30 days
```

**Per-node certificates (from nodes):**

```bash
# Check expiration on a specific node
ssh node001 "openssl x509 -in /var/lib/bcm-agent/certs/cert.pem -noout -enddate"

# Check all nodes via kubectl
for pod in $(kubectl get pods -n default -l app.kubernetes.io/name=bcm-agent -o name); do
  echo "=== $pod ==="
  kubectl exec -n default $pod -- \
    openssl x509 -in /var/lib/bcm-agent/certs/cert.pem -noout -subject -enddate
done
```

### Monitoring Script

Create a monitoring script to check all certificates:

```bash
cat > /tmp/check-bcm-certs.sh << 'EOF'
#!/bin/bash

NAMESPACE="default"
WARN_DAYS=30

echo "BCM Certificate Expiration Report"
echo "=================================="
echo ""

# Check bootstrap certificate
echo "Bootstrap Certificate:"
kubectl get secret bcm-bootstrap-cert -n $NAMESPACE \
  -o jsonpath='{.data.cert\.pem}' 2>/dev/null | \
  base64 -d | \
  openssl x509 -noout -subject -enddate

if kubectl get secret bcm-bootstrap-cert -n $NAMESPACE \
  -o jsonpath='{.data.cert\.pem}' | \
  base64 -d | \
  openssl x509 -noout -checkend $((WARN_DAYS * 86400)) 2>/dev/null; then
  echo "  Status: ✓ Valid for > $WARN_DAYS days"
else
  echo "  Status: ⚠ Expires within $WARN_DAYS days"
fi
echo ""

# Check per-node certificates
echo "Per-Node Certificates:"
for pod in $(kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=bcm-agent -o jsonpath='{.items[*].metadata.name}'); do
  node=$(kubectl get pod $pod -n $NAMESPACE -o jsonpath='{.spec.nodeName}')
  echo "  Node: $node"

  kubectl exec -n $NAMESPACE $pod -- \
    openssl x509 -in /var/lib/bcm-agent/certs/cert.pem -noout -enddate 2>/dev/null | \
    sed 's/^/    /'

  if kubectl exec -n $NAMESPACE $pod -- \
    openssl x509 -in /var/lib/bcm-agent/certs/cert.pem -noout -checkend $((WARN_DAYS * 86400)) 2>/dev/null; then
    echo "    Status: ✓ Valid for > $WARN_DAYS days"
  else
    echo "    Status: ⚠ Expires within $WARN_DAYS days"
  fi
  echo ""
done
EOF

chmod +x /tmp/check-bcm-certs.sh
./tmp/check-bcm-certs.sh
```

### Prometheus Monitoring

Add certificate expiration metrics:

```python
# In k8s_node_labeler.py or separate exporter
from prometheus_client import Gauge
import subprocess
import datetime

cert_expiration_gauge = Gauge(
    'bcm_cert_expiration_timestamp',
    'Certificate expiration timestamp',
    ['node', 'cert_type']
)

def get_cert_expiration(cert_path):
    """Get certificate expiration as Unix timestamp."""
    result = subprocess.run(
        ['openssl', 'x509', '-in', cert_path, '-noout', '-enddate'],
        capture_output=True, text=True
    )
    # Parse: notAfter=Nov 10 17:00:00 2026 GMT
    date_str = result.stdout.split('=')[1].strip()
    dt = datetime.datetime.strptime(date_str, '%b %d %H:%M:%S %Y %Z')
    return dt.timestamp()

# Update metrics
cert_expiration_gauge.labels(node=node_name, cert_type='per-node').set(
    get_cert_expiration('/var/lib/bcm-agent/certs/cert.pem')
)
```

**Prometheus alert rule:**

```yaml
groups:
  - name: bcm_certificates
    rules:
      - alert: BCMCertificateExpiringSoon
        expr: (bcm_cert_expiration_timestamp - time()) < 2592000  # 30 days
        labels:
          severity: warning
        annotations:
          summary: "BCM certificate expiring soon on {{ $labels.node }}"
          description: "Certificate for {{ $labels.node }} expires in less than 30 days"

      - alert: BCMCertificateExpired
        expr: (bcm_cert_expiration_timestamp - time()) < 0
        labels:
          severity: critical
        annotations:
          summary: "BCM certificate expired on {{ $labels.node }}"
          description: "Certificate for {{ $labels.node }} has expired"
```

## Certificate Rotation

### Rotating Bootstrap Certificate

Bootstrap certificates should be rotated annually or before expiration.

**Step 1: Create new bootstrap certificate**

```bash
# On BCM head node
python3 /tmp/create_bootstrap_cert.py  # Creates new cert in /tmp/k8s-bootstrap-cert/

# Verify new certificate
openssl x509 -in /tmp/k8s-bootstrap-cert/cert.pem -noout -dates
```

**Step 2: Update Kubernetes Secret**

```bash
# Option A: Replace Secret
kubectl delete secret bcm-bootstrap-cert -n default
kubectl create secret generic bcm-bootstrap-cert \
  --from-file=cacert.pem=/tmp/k8s-bootstrap-cert/cacert.pem \
  --from-file=cert.pem=/tmp/k8s-bootstrap-cert/cert.pem \
  --from-file=cert.key=/tmp/k8s-bootstrap-cert/cert.key \
  --namespace default

# Option B: Update Secret in-place
kubectl create secret generic bcm-bootstrap-cert \
  --from-file=cacert.pem=/tmp/k8s-bootstrap-cert/cacert.pem \
  --from-file=cert.pem=/tmp/k8s-bootstrap-cert/cert.pem \
  --from-file=cert.key=/tmp/k8s-bootstrap-cert/cert.key \
  --namespace default \
  --dry-run=client -o yaml | kubectl apply -f -
```

**Step 3: Restart pods to pick up new Secret**

```bash
# Restart DaemonSet (rolling restart)
kubectl rollout restart daemonset/bcm-agent -n default

# Watch rollout
kubectl rollout status daemonset/bcm-agent -n default
```

**Step 4: Revoke old bootstrap certificate**

```bash
# On BCM head node
# Find old certificate by serial number or common name
# Then revoke using pythoncm (see Revocation section)
```

### Rotating Per-Node Certificates

Per-node certificates should be rotated every 30-90 days or before expiration.

**Option 1: Rolling rotation (one node at a time)**

```bash
# For each node
for pod in $(kubectl get pods -n default -l app.kubernetes.io/name=bcm-agent -o name); do
  echo "Rotating certificate for $pod"

  # Delete per-node certificate on the node
  kubectl exec -n default $pod -- rm -f /var/lib/bcm-agent/certs/cert.pem /var/lib/bcm-agent/certs/cert.key

  # Restart pod to regenerate certificate
  kubectl delete -n default $pod

  # Wait for pod to be ready
  kubectl wait -n default --for=condition=Ready $pod --timeout=120s

  echo "✓ Certificate rotated for $pod"
  sleep 10  # Wait before next node
done
```

**Option 2: Batch rotation (all nodes at once)**

```bash
# Delete all per-node certificates via SSH
for node in node001 node002 node003; do
  ssh $node "rm -f /var/lib/bcm-agent/certs/cert.pem /var/lib/bcm-agent/certs/cert.key"
done

# Restart DaemonSet
kubectl rollout restart daemonset/bcm-agent -n default
kubectl rollout status daemonset/bcm-agent -n default
```

**Option 3: Automated rotation with CronJob**

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: bcm-cert-rotator
  namespace: default
spec:
  schedule: "0 2 1 * *"  # Monthly at 2 AM on the 1st
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: bcm-cert-rotator
          containers:
          - name: rotator
            image: quay.io/your-org/bcm-cert-rotator:1.0
            command:
            - /bin/bash
            - -c
            - |
              # Check certificate expiration
              for pod in $(kubectl get pods -n default -l app.kubernetes.io/name=bcm-agent -o name); do
                # Get days until expiration
                days=$(kubectl exec -n default $pod -- \
                  openssl x509 -in /var/lib/bcm-agent/certs/cert.pem -noout -enddate | \
                  # Calculate days remaining
                )

                if [ $days -lt 30 ]; then
                  echo "Rotating certificate for $pod (expires in $days days)"
                  kubectl exec -n default $pod -- \
                    rm -f /var/lib/bcm-agent/certs/cert.pem /var/lib/bcm-agent/certs/cert.key
                  kubectl delete -n default $pod
                fi
              done
          restartPolicy: OnFailure
```

## Certificate Revocation

### Revoking Certificates with pythoncm

```bash
# On BCM head node
cat > /tmp/revoke_cert.py << 'EOF'
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/cm/local/apps/cmd/pythoncm/lib/python3.12/site-packages')

from pythoncm.cluster import Cluster
from pythoncm.settings import Settings

# Connect to BCM
settings = Settings(
    host="localhost",
    port=8081,
    cert_file="/cm/local/apps/cmd/etc/cert.pem",
    key_file="/cm/local/apps/cmd/etc/cert.key"
)
cluster = Cluster(settings)

# Get certificate by common name
cert_cn = sys.argv[1] if len(sys.argv) > 1 else "node001"
certs = cluster.list_certificates()
cert = next((c for c in certs if c.commonName == cert_cn), None)

if not cert:
    print(f"✗ Certificate not found: {cert_cn}")
    sys.exit(1)

print(f"Found certificate: {cert_cn}")
print(f"  Serial: {cert.serial}")
print(f"  Status: {cert.status}")
print(f"  Valid from: {cert.validFrom}")
print(f"  Valid to: {cert.validTo}")

# Revoke certificate
if cert.status == "issued":
    cert.revoke()
    print(f"✓ Certificate revoked: {cert_cn}")
else:
    print(f"Certificate already revoked: {cert_cn}")
EOF

chmod +x /tmp/revoke_cert.py

# Revoke certificate by common name
python3 /tmp/revoke_cert.py node001
```

### Revoking via cmsh

```bash
# On BCM head node
cmsh -c "cert; list" | grep node001

# Revoke by certificate name
cmsh -c "cert; use <cert-name>; revoke; commit"
```

### Bulk Revocation

```bash
# Revoke all per-node certificates for a cluster
cat > /tmp/revoke_cluster_certs.py << 'EOF'
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/cm/local/apps/cmd/pythoncm/lib/python3.12/site-packages')

from pythoncm.cluster import Cluster
from pythoncm.settings import Settings

# Connect to BCM
settings = Settings(
    host="localhost",
    port=8081,
    cert_file="/cm/local/apps/cmd/etc/cert.pem",
    key_file="/cm/local/apps/cmd/etc/cert.key"
)
cluster = Cluster(settings)

# Revoke all certificates matching pattern
pattern = sys.argv[1] if len(sys.argv) > 1 else "node"
certs = cluster.list_certificates()

for cert in certs:
    if pattern in cert.commonName and cert.status == "issued":
        print(f"Revoking: {cert.commonName} (serial: {cert.serial})")
        cert.revoke()

print(f"✓ Revoked all certificates matching: {pattern}")
EOF

python3 /tmp/revoke_cluster_certs.py "node"
```

## Troubleshooting

### Certificate Expired

**Symptom:** Pods fail with "certificate has expired"

**Solution:**

```bash
# For bootstrap certificate:
# 1. Create new bootstrap certificate
# 2. Update Secret
# 3. Restart pods

# For per-node certificate:
# Delete certificate and restart pod
kubectl exec <pod-name> -n default -- \
  rm -f /var/lib/bcm-agent/certs/cert.pem /var/lib/bcm-agent/certs/cert.key
kubectl delete pod <pod-name> -n default
```

### Certificate Verify Failed

**Symptom:** "SSL: CERTIFICATE_VERIFY_FAILED"

**Common causes:**
1. CA certificate mismatch
2. Certificate not yet valid (clock skew)
3. Certificate revoked
4. Wrong certificate being used

**Diagnosis:**

```bash
# Check certificate details
kubectl exec <pod-name> -n default -- \
  openssl x509 -in /var/lib/bcm-agent/certs/cert.pem -noout -text

# Verify certificate chain
kubectl exec <pod-name> -n default -- \
  openssl verify -CAfile /var/lib/bcm-agent/certs/cacert.pem \
    /var/lib/bcm-agent/certs/cert.pem

# Check if revoked (on BCM head node)
# Query certificate status in BCM database
```

### Permission Denied

**Symptom:** Certificate request fails with "permission denied"

**Cause:** Bootstrap certificate lacks permissions

**Solution:**

Check bootstrap certificate profile has certificate request permissions:

```bash
# On BCM head node
cmsh -c "cert; use k8s-bootstrap; show profile"

# Profile should allow certificate requests
# If not, update profile or recreate bootstrap certificate with correct profile
```

## Automation

### Automated Certificate Monitoring

Set up a CronJob to monitor certificate expiration:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: bcm-cert-monitor
  namespace: default
spec:
  schedule: "0 8 * * *"  # Daily at 8 AM
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: bcm-cert-monitor
          containers:
          - name: monitor
            image: quay.io/your-org/bcm-cert-monitor:1.0
            command:
            - /bin/bash
            - -c
            - |
              /tmp/check-bcm-certs.sh | mail -s "BCM Certificate Report" admin@example.com
          restartPolicy: OnFailure
```

### Automated Certificate Rotation

Integrate with cert-manager or create custom operator:

```go
// Pseudocode for BCM certificate operator
func (r *CertificateReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // Get all bcm-agent pods
    pods := r.listBCMAgentPods()

    for _, pod := range pods {
        // Check certificate expiration
        daysRemaining := r.getCertificateDaysRemaining(pod)

        if daysRemaining < 30 {
            // Delete certificate on node
            r.deleteCertificate(pod)

            // Restart pod to regenerate
            r.restartPod(pod)

            log.Info("Rotated certificate", "pod", pod.Name, "daysRemaining", daysRemaining)
        }
    }

    return ctrl.Result{RequeueAfter: 24 * time.Hour}, nil
}
```

## Best Practices

1. **Bootstrap Certificates:**
   - Long validity (1-2 years)
   - Minimal permissions (certificate requests only)
   - One per Kubernetes cluster
   - Rotate annually

2. **Per-Node Certificates:**
   - Short validity (30-90 days)
   - Full node permissions
   - Unique per node
   - Rotate before expiration

3. **Monitoring:**
   - Alert when certificates expire in < 30 days
   - Monitor certificate expiration daily
   - Track certificate usage and failures

4. **Security:**
   - Protect bootstrap Secret with RBAC
   - Never expose private keys
   - Revoke compromised certificates immediately
   - Audit certificate access logs

5. **Automation:**
   - Automate certificate rotation
   - Monitor certificate health
   - Test rotation procedures regularly

## Related Documentation

- [Bootstrap Certificate Setup](BOOTSTRAP_CERTIFICATES.md)
- [Kubernetes Deployment Guide](KUBERNETES_DEPLOYMENT.md)
- [Main README](../README.md)
