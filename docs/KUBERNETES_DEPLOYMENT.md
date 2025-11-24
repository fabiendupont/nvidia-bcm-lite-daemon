# Kubernetes/OpenShift Deployment Guide

Complete guide for deploying bcm-agent on Kubernetes and OpenShift clusters using Helm.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Architecture Overview](#architecture-overview)
- [Deployment Steps](#deployment-steps)
  - [1. Build Container Image](#1-build-container-image)
  - [2. Setup Bootstrap Certificates](#2-setup-bootstrap-certificates)
  - [3. Deploy via Helm](#3-deploy-via-helm)
  - [4. Verify Deployment](#4-verify-deployment)
- [Configuration](#configuration)
- [Upgrading](#upgrading)
- [Troubleshooting](#troubleshooting)
- [Production Recommendations](#production-recommendations)

## Prerequisites

**Required:**
- Kubernetes 1.24+ or OpenShift 4.12+
- Helm 3.0+
- Access to BCM head node (port 8081)
- Cluster admin access (for ClusterRole to patch nodes)
- Container image registry (quay.io, internal registry, etc.)

**BCM Requirements:**
- BCM head node with `cmdaemon` running
- Bootstrap certificate created (see [Bootstrap Certificate Guide](BOOTSTRAP_CERTIFICATES.md))
- Network connectivity from cluster to BCM head node port 8081

**Tools:**
- `kubectl` or `oc` CLI configured
- `helm` CLI installed
- `podman` or `docker` for building images

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ BCM Head Node (10.141.255.254)                                   │
│  ┌────────────────────────┐                                      │
│  │ cmdaemon (port 8081)    │                                      │
│  │ - WebSocket server      │                                      │
│  │ - Certificate authority │                                      │
│  │ - Node inventory        │                                      │
│  └────────────────────────┘                                      │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ TLS WebSocket
                 │ Per-node certificates
                 │
┌────────────────▼────────────────────────────────────────────────┐
│ Kubernetes/OpenShift Cluster                                     │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Namespace: default (or custom)                            │  │
│  │                                                            │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │ Secret: bcm-bootstrap-cert                         │  │  │
│  │  │  - cacert.pem (BCM CA)                             │  │  │
│  │  │  - cert.pem (bootstrap certificate)                │  │  │
│  │  │  - cert.key (bootstrap private key)                │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  │                                                            │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │ DaemonSet: bcm-agent                               │  │  │
│  │  │                                                      │  │  │
│  │  │  Pod (one per node):                               │  │  │
│  │  │  ├─> entrypoint.sh                                 │  │  │
│  │  │  │   ├─> Detect bootstrap certificates            │  │  │
│  │  │  │   ├─> Generate per-node cert (if needed)       │  │  │
│  │  │  │   └─> Start cm-lite-daemon + node labeler      │  │  │
│  │  │  ├─> cm-lite-daemon                                │  │  │
│  │  │  │   ├─> Connect to BCM via WebSocket             │  │  │
│  │  │  │   ├─> Collect hardware metrics                 │  │  │
│  │  │  │   └─> Report status to BCM                     │  │  │
│  │  │  └─> k8s_node_labeler.py                          │  │  │
│  │  │      ├─> Read BCM data                            │  │  │
│  │  │      ├─> Apply node labels                        │  │  │
│  │  │      └─> Export Prometheus metrics (port 9100)    │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  │                                                            │  │
│  │  HostPath volumes (per node):                             │  │
│  │  └─> /var/lib/bcm-agent/certs/                            │  │
│  │      ├─> cert.pem (per-node certificate)                  │  │
│  │      ├─> cert.key (per-node private key)                  │  │
│  │      └─> cacert.pem (BCM CA)                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
└──────────────────────────────────────────────┬──────────────────┘
                                                │
                                                ↓
                                    Kubernetes API Server
                                    (node labels, metrics)
```

## Deployment Steps

### 1. Build Container Image

⚠️ **IMPORTANT**: Container images must be built on the BCM head node or a system with access to NVIDIA's proprietary cm-lite-daemon distribution.

**Using the build script (Recommended):**

```bash
# On BCM head node
cd /path/to/nvidia-bcm-lite-daemon

# Build and tag for your registry
./scripts/build-image.sh \
  --registry quay.io/YOUR_ORG \
  --tag 1.0.2 \
  --push

# Or build for OpenShift internal registry
./scripts/build-image.sh \
  --openshift \
  --tag 1.0.2 \
  --push
```

**Manual build process:**

```bash
# On BCM head node
cd /path/to/nvidia-bcm-lite-daemon

# Copy NVIDIA cm-lite-daemon distribution to build context
cp /cm/shared/apps/cm-lite-daemon-dist/cm-lite-daemon.zip .

# Build image
podman build -t bcm-agent:1.0.2 .

# Tag for your registry
podman tag bcm-agent:1.0.2 quay.io/YOUR_ORG/bcm-agent:1.0.2

# Push to registry
podman login quay.io
podman push quay.io/YOUR_ORG/bcm-agent:1.0.2

# Clean up proprietary file
rm cm-lite-daemon.zip
```

**For OpenShift internal registry:**

```bash
# On BCM head node
cd /path/to/nvidia-bcm-lite-daemon

# Copy cm-lite-daemon.zip
cp /cm/shared/apps/cm-lite-daemon-dist/cm-lite-daemon.zip .

# Build
podman build -t bcm-agent:1.0.2 .

# Login to OpenShift internal registry
oc login
TOKEN=$(oc whoami -t)
podman login -u unused -p $TOKEN default-route-openshift-image-registry.apps.YOUR_DOMAIN

# Tag and push
podman tag bcm-agent:1.0.2 default-route-openshift-image-registry.apps.YOUR_DOMAIN/default/bcm-agent:1.0.2
podman push default-route-openshift-image-registry.apps.YOUR_DOMAIN/default/bcm-agent:1.0.2

# Clean up
rm cm-lite-daemon.zip
```

**For private registry (k3s, minikube):**

```bash
# Build on BCM head node first
cp /cm/shared/apps/cm-lite-daemon-dist/cm-lite-daemon.zip .
podman build -t bcm-agent:1.0.2 .
rm cm-lite-daemon.zip

# Save and transfer image
podman save bcm-agent:1.0.2 | ssh root@k8s-node "ctr -n k8s.io images import -"

# Or load into Docker/containerd
podman save bcm-agent:1.0.2 -o bcm-agent-1.0.2.tar
scp bcm-agent-1.0.2.tar k8s-node:/tmp/
ssh k8s-node "ctr -n k8s.io images import /tmp/bcm-agent-1.0.2.tar"
```

**Note:** The resulting container image contains NVIDIA proprietary software and should NOT be redistributed publicly.

### 2. Setup Bootstrap Certificates

**Detailed steps:** See [Bootstrap Certificate Setup Guide](BOOTSTRAP_CERTIFICATES.md)

**Quick setup:**

```bash
# On BCM head node - create bootstrap certificate
cd /cm/local/apps/cm-lite-daemon
mkdir -p /tmp/bootstrap-cert

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

# Create Kubernetes Secret
kubectl create secret generic bcm-bootstrap-cert \
  --from-file=cacert.pem=/tmp/bootstrap-cert/cacert.pem \
  --from-file=cert.pem=/tmp/bootstrap-cert/cert.pem \
  --from-file=cert.key=/tmp/bootstrap-cert/cert.key \
  --namespace default

# Verify Secret
kubectl get secret bcm-bootstrap-cert -n default
kubectl describe secret bcm-bootstrap-cert -n default
```

### 3. Deploy via Helm

**Basic deployment:**

```bash
cd /root/bcm/bcm-agent

# Install bcm-agent
helm install bcm-agent ./helm/bcm-agent \
  --namespace default \
  --set image.repository=quay.io/YOUR_ORG/bcm-agent \
  --set image.tag=1.0.2 \
  --set config.bcm.host=10.141.255.254 \
  --set config.bcm.port=8081 \
  --set certificates.secretName=bcm-bootstrap-cert
```

**Production deployment with custom values:**

```bash
# Create values file
cat > values-prod.yaml << 'EOF'
image:
  repository: quay.io/YOUR_ORG/bcm-agent
  tag: "1.0.2"
  pullPolicy: IfNotPresent

config:
  bcm:
    host: "bcmhead.example.com"
    port: 8081

  kubernetes:
    syncInterval: 300
    labelPrefix: "bcm.nvidia.com"
    enableLabeling: true

certificates:
  secretName: "bcm-bootstrap-cert"

metrics:
  enabled: true
  port: 9100

resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"

# Run on all nodes (including masters)
tolerations:
  - operator: Exists

# High priority for critical monitoring
priorityClassName: "system-node-critical"

# Node selector (optional - run only on specific nodes)
# nodeSelector:
#   node-role.kubernetes.io/worker: ""
EOF

# Deploy with values file
helm install bcm-agent ./helm/bcm-agent \
  --namespace default \
  --values values-prod.yaml
```

**OpenShift-specific deployment:**

```bash
# Create namespace with proper annotations
oc new-project bcm-agent \
  --description="NVIDIA BCM Agent" \
  --display-name="BCM Agent"

# Allow privileged containers (if not already allowed)
oc adm policy add-scc-to-user privileged -z bcm-agent -n bcm-agent

# Deploy with OpenShift registry
helm install bcm-agent ./helm/bcm-agent \
  --namespace bcm-agent \
  --set image.repository=image-registry.openshift-image-registry.svc:5000/bcm-agent/bcm-agent \
  --set image.tag=1.0.2 \
  --set config.bcm.host=10.141.255.254 \
  --set certificates.secretName=bcm-bootstrap-cert
```

### 4. Verify Deployment

**Check DaemonSet and Pods:**

```bash
# Get DaemonSet status
kubectl get daemonset bcm-agent -n default

# Expected output:
# NAME        DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE
# bcm-agent   3         3         3       3            3

# Get pod status
kubectl get pods -l app.kubernetes.io/name=bcm-agent -n default -o wide

# Expected output:
# NAME              READY   STATUS    RESTARTS   AGE   IP           NODE
# bcm-agent-abc12   1/1     Running   0          2m    10.1.1.10    node001
# bcm-agent-def34   1/1     Running   0          2m    10.1.1.20    node002
# bcm-agent-ghi56   1/1     Running   0          2m    10.1.1.30    node003
```

**Check logs for bootstrap certificate generation:**

```bash
# View logs from one pod
kubectl logs -n default bcm-agent-abc12 --tail=50

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
# ✓ Per-node certificate generated successfully
# Using per-node certificates from: /var/lib/bcm-agent/certs
# Starting cm-lite-daemon...
# INFO     Websocket connected
# INFO     CMDaemon started
# INFO     [k8s_node_labeler.py] Starting BCM Node Labeler for node001
```

**Verify per-node certificates on nodes:**

```bash
# Check certificate files on a node
kubectl get pod bcm-agent-abc12 -o jsonpath='{.spec.nodeName}'
# Output: node001

# SSH to the node
ssh node001 "ls -la /var/lib/bcm-agent/certs/"

# Expected output:
# total 16
# -r--------. 1 root root 4356 Nov 10 18:11 cacert.pem
# -rw-------. 1 root root 1704 Nov 10 18:05 cert.key
# -rw-------. 1 root root 1338 Nov 10 18:05 cert.pem

# Verify certificate CN matches node name
ssh node001 "openssl x509 -in /var/lib/bcm-agent/certs/cert.pem -noout -subject"

# Expected output:
# subject=C=US, ST=California, L=Santa Clara, O=NVIDIA Inc, OU=Bright Licensing, CN=node001
```

**Check node labels:**

```bash
# View BCM labels on nodes
kubectl get nodes --show-labels | grep bcm.nvidia.com

# View labels for specific node
kubectl describe node node001 | grep bcm.nvidia.com

# Expected labels:
#   bcm.nvidia.com/node-name=node001
#   bcm.nvidia.com/bcm-cluster=bcmhead
#   (additional labels based on hardware)
```

**Verify Prometheus metrics:**

```bash
# Port-forward to metrics endpoint
kubectl port-forward -n default daemonset/bcm-agent 9100:9100 &

# Query metrics
curl -s http://localhost:9100/metrics | grep bcm_

# Expected metrics:
# bcm_node_info{node="node001",bcm_cluster="bcmhead"} 1
# bcm_hardware_health{node="node001",component="gpu"} 1
# bcm_last_sync_timestamp{node="node001"} 1699876543
```

**Verify BCM connection:**

```bash
# On BCM head node - check active sessions
cmsh -c "session; list" | grep bcm-agent

# Or check specific node
cmsh -c "device; use node001; show"

# Verify node is connected (should show status as UP)
```

## Configuration

### Helm Values Reference

**Image configuration:**
```yaml
image:
  repository: ghcr.io/fabiendupont/nvidia-bcm-lite-daemon
  tag: "1.0.2"
  pullPolicy: IfNotPresent
  pullSecrets: []  # List of image pull secrets if registry requires auth
```

**BCM connection:**
```yaml
config:
  bcm:
    host: "10.141.255.254"  # BCM head node hostname or IP
    port: 8081               # cmdaemon WebSocket port
```

**Kubernetes integration:**
```yaml
config:
  kubernetes:
    syncInterval: 300                    # Label sync interval (seconds)
    labelPrefix: "bcm.nvidia.com"        # Node label prefix
    enableLabeling: true                 # Enable node labeling
    disableLabeling: false               # Disable labeling (metrics only mode)
```

**Certificates:**
```yaml
certificates:
  secretName: "bcm-bootstrap-cert"  # Name of bootstrap certificate Secret
```

**Metrics:**
```yaml
metrics:
  enabled: true   # Enable Prometheus metrics
  port: 9100      # Metrics endpoint port
```

**Resources:**
```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

**Node scheduling:**
```yaml
# Run on all nodes (default)
tolerations:
  - operator: Exists

# Or run only on worker nodes
nodeSelector:
  node-role.kubernetes.io/worker: ""

# Priority class for important workloads
priorityClassName: "system-node-critical"
```

**Security context:**
```yaml
securityContext:
  privileged: true  # Required for hardware access (dmidecode, IPMI, etc.)
  # Alternative: use specific capabilities
  # capabilities:
  #   add:
  #     - SYS_ADMIN
  #     - SYS_RAWIO
```

## Upgrading

### Upgrade to New Image Version

```bash
# Update image tag
helm upgrade bcm-agent ./helm/bcm-agent \
  --namespace default \
  --set image.tag=1.0.3 \
  --reuse-values

# Watch rollout
kubectl rollout status daemonset/bcm-agent -n default

# Verify new version
kubectl get pods -n default -l app.kubernetes.io/name=bcm-agent \
  -o jsonpath='{.items[0].spec.containers[0].image}'
```

### Upgrade Configuration

```bash
# Update configuration values
helm upgrade bcm-agent ./helm/bcm-agent \
  --namespace default \
  --set config.kubernetes.syncInterval=600 \
  --reuse-values

# Or update with new values file
helm upgrade bcm-agent ./helm/bcm-agent \
  --namespace default \
  --values values-prod-updated.yaml
```

### Upgrade Chart Version

```bash
# Pull updated chart
cd /root/bcm/bcm-agent
git pull

# Upgrade with new chart
helm upgrade bcm-agent ./helm/bcm-agent \
  --namespace default \
  --reuse-values

# Check upgrade history
helm history bcm-agent -n default
```

### Rollback

```bash
# List revision history
helm history bcm-agent -n default

# Rollback to previous version
helm rollback bcm-agent -n default

# Rollback to specific revision
helm rollback bcm-agent 2 -n default
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n default -l app.kubernetes.io/name=bcm-agent

# Check events
kubectl get events -n default --sort-by='.lastTimestamp' | grep bcm-agent

# Describe pod for details
kubectl describe pod <pod-name> -n default

# Common issues:
# - Image pull errors (check registry access, image name)
# - Secret not found (verify bcm-bootstrap-cert exists)
# - Insufficient privileges (check SecurityContext/SCC)
# - Resource limits too low
```

### Certificate Generation Fails

```bash
# View pod logs
kubectl logs <pod-name> -n default

# Check for connection errors:
# - "Connection refused" → BCM host unreachable
# - "Certificate verify failed" → CA certificate mismatch
# - "Permission denied" → Bootstrap cert lacks permissions

# Test connectivity from pod
kubectl exec <pod-name> -n default -- ping -c 3 10.141.255.254
kubectl exec <pod-name> -n default -- timeout 5 bash -c '</dev/tcp/10.141.255.254/8081' && echo "Connected"

# Verify bootstrap Secret
kubectl get secret bcm-bootstrap-cert -n default -o yaml

# Check bootstrap certificate validity
kubectl get secret bcm-bootstrap-cert -n default -o jsonpath='{.data.cert\.pem}' | \
  base64 -d | openssl x509 -noout -dates
```

### cm-lite-daemon Not Connecting

```bash
# Check logs
kubectl logs <pod-name> -n default | grep -A10 "cm-lite"

# Look for:
# - "Websocket connected" → Success
# - "WebSocket error" → Connection failed
# - "Certificate verify failed" → SSL/TLS issue

# Verify per-node certificate exists
kubectl exec <pod-name> -n default -- ls -la /var/lib/bcm-agent/certs/

# Check certificate validity
kubectl exec <pod-name> -n default -- \
  openssl x509 -in /var/lib/bcm-agent/certs/cert.pem -noout -dates

# Test BCM connectivity
kubectl exec <pod-name> -n default -- \
  timeout 10 openssl s_client -connect 10.141.255.254:8081 \
    -CAfile /var/lib/bcm-agent/certs/cacert.pem \
    -cert /var/lib/bcm-agent/certs/cert.pem \
    -key /var/lib/bcm-agent/certs/cert.key
```

### Node Labels Not Applied

```bash
# Check RBAC permissions
kubectl auth can-i patch nodes --as=system:serviceaccount:default:bcm-agent

# Should return: yes
# If no, check ClusterRole and ClusterRoleBinding

# View labeler logs
kubectl logs <pod-name> -n default | grep k8s_node_labeler

# Check for errors:
# - "Forbidden" → RBAC issue
# - "Connection refused" → Cannot reach Kubernetes API
# - "No data from cm-lite-daemon" → cm-lite-daemon not running

# Manually test label application
kubectl label nodes node001 test.example.com/test=value
# If this fails, check RBAC
```

### Metrics Not Available

```bash
# Check if metrics port is listening
kubectl exec <pod-name> -n default -- netstat -tlnp | grep 9100

# Test metrics endpoint from inside pod
kubectl exec <pod-name> -n default -- curl http://localhost:9100/metrics

# Port-forward and test externally
kubectl port-forward <pod-name> -n default 9100:9100 &
curl http://localhost:9100/metrics

# Check service
kubectl get svc bcm-agent -n default
kubectl describe svc bcm-agent -n default
```

### High Memory Usage

```bash
# Check current usage
kubectl top pod -n default -l app.kubernetes.io/name=bcm-agent

# Increase memory limit
helm upgrade bcm-agent ./helm/bcm-agent \
  --namespace default \
  --set resources.limits.memory=1Gi \
  --reuse-values

# Check for memory leaks in logs
kubectl logs <pod-name> -n default | grep -i "memory\|oom"
```

## Production Recommendations

### High Availability

```yaml
# Ensure DaemonSet runs on all critical nodes
tolerations:
  - operator: Exists  # Run on all nodes including masters

# Use priority class for critical workloads
priorityClassName: "system-node-critical"

# Set resource limits to prevent resource exhaustion
resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

### Security

```yaml
# Use least-privilege SecurityContext where possible
# Note: privileged mode may be required for hardware access
securityContext:
  runAsNonRoot: false  # Required for hardware access (dmidecode, IPMI)
  readOnlyRootFilesystem: false  # Need to write to /var/run, /var/log

# Restrict network policies (if applicable)
# Allow egress to BCM head node only
```

### Monitoring

```yaml
# Enable ServiceMonitor for Prometheus Operator
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: bcm-agent
  namespace: default
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: bcm-agent
  endpoints:
    - port: metrics
      interval: 60s
      path: /metrics
```

### Certificate Rotation

```bash
# Set up certificate expiration monitoring
# Alert when certificates expire in < 30 days

# Automate rotation (cron job or operator)
# 1. Check certificate expiration
# 2. If < 30 days, delete per-node certs
# 3. Restart pods to regenerate
```

### Logging

```yaml
# Configure log collection (FluentBit, Fluentd)
# Collect logs from:
# - /var/log/bcm-agent/cm-lite-daemon.log
# - kubectl logs output

# Set appropriate log level
config:
  debug: false  # Disable in production
  logLevel: "info"  # Use "debug" only for troubleshooting
```

### Backup and Disaster Recovery

```bash
# Backup bootstrap Secret
kubectl get secret bcm-bootstrap-cert -n default -o yaml > bcm-bootstrap-cert-backup.yaml

# Backup Helm values
helm get values bcm-agent -n default > bcm-agent-values-backup.yaml

# Backup per-node certificates (optional)
# Certificates can be regenerated automatically
# Only backup if you need to preserve specific serial numbers
```

## Related Documentation

- [Bootstrap Certificate Setup Guide](BOOTSTRAP_CERTIFICATES.md) - Detailed certificate setup
- [Certificate Management](CERTIFICATE_MANAGEMENT.md) - Certificate lifecycle management
- [Main README](../README.md) - Project overview
- [Helm Chart README](../helm/bcm-agent/README.md) - Helm chart reference

## Support

For issues and questions:
- Check logs: `kubectl logs -n default -l app.kubernetes.io/name=bcm-agent`
- Review troubleshooting section above
- Consult BCM documentation for BCM-specific issues
