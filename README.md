# NVIDIA BCM Lite Daemon

**Lightweight BCM integration for Kubernetes/OpenShift and RHEL using cm-lite-daemon**

## Overview

NVIDIA BCM Lite Daemon provides seamless integration between NVIDIA Base Command Manager (BCM) and both Kubernetes/OpenShift clusters and standalone RHEL servers. It runs NVIDIA's official `cm-lite-daemon` to establish two-way communication with the BCM head node, enabling:

- ✅ **Hardware monitoring** - Real-time sync of GPU, CPU, memory, InfiniBand, and BMC status
- ✅ **Inventory sync** - Node metadata synchronized between BCM and OpenShift
- ✅ **Node labeling** - Hardware-based labels for intelligent workload scheduling
- ✅ **Prometheus metrics** - Integration with OpenShift monitoring stack
- ✅ **Closes the loop** - Deployed OpenShift cluster communicates back to BCM head node

## Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│ BCM Head Node (bcmhead)                                           │
│  ┌──────────────────────────┐                                     │
│  │ cmdaemon (port 8081)     │                                     │
│  │ - WebSocket server       │                                     │
│  │ - Node inventory         │                                     │
│  │ - Hardware monitoring    │                                     │
│  └──────────────────────────┘                                     │
└────────────────┬──────────────────────────────────────────────────┘
                 │
                 │ WebSocket (TLS)
                 │ Certificate-based auth
                 │
┌────────────────▼──────────────────────────────────────────────────┐
│ OpenShift Cluster                                                 │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │ BCM Agent DaemonSet (Helm Chart)                           │   │
│  │                                                            │   │
│  │  Pod per node:                                             │   │
│  │  ├─> cm-lite-daemon (NVIDIA official)                      │   │
│  │  │   ├─> WebSocket client → BCM head node                  │   │
│  │  │   ├─> Hardware data collection                          │   │
│  │  │   └─> Two-way communication with BCM                    │   │
│  │  └─> K8s Node Labeler                                      │   │
│  │      ├─> Reads BCM data from cm-lite-daemon                │   │
│  │      ├─> Applies node labels via Kubernetes API            │   │
│  │      └─> Exports Prometheus metrics                        │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                   │
└────────────────────────────────┬──────────────────────────────────┘
                                 │
                                 ↓
                        Kubernetes API
                   (node labels, metrics)
```

### Component Roles

- **cm-lite-daemon**: NVIDIA's official lightweight daemon for BCM compute nodes
  - Establishes WebSocket connection to BCM head node
  - Collects hardware metrics (GPUs, CPUs, memory, InfiniBand, BMC)
  - Sends node status updates to BCM
  - Receives commands from BCM (future: firmware updates, configuration)

- **K8s Node Labeler**: Custom Kubernetes integration component
  - Reads hardware data from cm-lite-daemon
  - Applies labels to Kubernetes nodes for scheduling
  - Exports Prometheus metrics for monitoring

- **BCM Head Node**: Centralized cluster management
  - Maintains node inventory and hardware database
  - Manages firmware and configuration
  - Provides WebSocket endpoint for cm-lite-daemon connections

## Documentation

**Comprehensive deployment and operations guides are available in the [docs/](docs/) directory:**

- **[Kubernetes Deployment Guide](docs/KUBERNETES_DEPLOYMENT.md)** - Complete step-by-step deployment for Kubernetes/OpenShift
- **[Bootstrap Certificate Setup](docs/BOOTSTRAP_CERTIFICATES.md)** - Automatic per-node certificate provisioning
- **[Certificate Management](docs/CERTIFICATE_MANAGEMENT.md)** - Certificate lifecycle, rotation, and monitoring
- **[Documentation Index](docs/README.md)** - Full documentation overview

**Quick references:**
- [Helm Chart README](helm/bcm-agent/README.md) - Helm configuration parameters
- [Architecture Decision](ARCHITECTURE_DECISION.md) - Design rationale and decisions

For detailed deployment instructions, see the [Kubernetes Deployment Guide](docs/KUBERNETES_DEPLOYMENT.md).

## Quick Start

### Prerequisites

- **OpenShift 4.12+ or Kubernetes 1.24+**
- **Helm 3.0+**
- **BCM head node** with cmdaemon running (port 8081 accessible from cluster)
- **Bootstrap certificate** for automatic per-node certificate provisioning
  - See [Bootstrap Certificate Setup Guide](docs/BOOTSTRAP_CERTIFICATES.md) for detailed instructions
- **Cluster admin access** (required for ClusterRole to patch nodes)

### Installation

> **Note:** For complete deployment instructions, see the [Kubernetes Deployment Guide](docs/KUBERNETES_DEPLOYMENT.md).

#### Step 1: Create Bootstrap Certificate Secret

The bcm-agent uses **bootstrap certificates** to automatically generate unique per-node certificates on first startup.

```bash
# On BCM head node - create bootstrap certificate (one-time setup)
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
```

**What happens next:** Each pod will automatically generate a unique per-node certificate (CN=nodename) on first startup. See [Bootstrap Certificate Setup](docs/BOOTSTRAP_CERTIFICATES.md) for details.

#### Step 2: Build Container Image

⚠️ **IMPORTANT**: The container image must be built on your BCM head node as it requires NVIDIA's proprietary cm-lite-daemon.

```bash
# On BCM head node
cd /path/to/nvidia-bcm-lite-daemon

# Copy NVIDIA cm-lite-daemon distribution
cp /cm/shared/apps/cm-lite-daemon-dist/cm-lite-daemon.zip .

# Build image
podman build -t bcm-agent:latest .

# Tag for your registry
podman tag bcm-agent:latest <your-registry>/bcm-agent:latest

# Push to registry (optional)
podman push <your-registry>/bcm-agent:latest

# Clean up
rm cm-lite-daemon.zip
```

See the [Building](#building) section for detailed instructions including pushing to OpenShift internal registry.

#### Step 3: Deploy via Helm

```bash
# Install BCM Agent
helm install bcm-agent ./helm/bcm-agent \
  --namespace default \
  --set image.repository=ghcr.io/fabiendupont/nvidia-bcm-lite-daemon \
  --set image.tag=latest \
  --set config.bcm.host=10.141.255.254 \
  --set config.bcm.port=8081 \
  --set certificates.secretName=bcm-bootstrap-cert
```

The DaemonSet will deploy one pod per node. Each pod will:
1. Detect the bootstrap certificate in the Secret
2. Automatically generate a unique per-node certificate (CN=nodename)
3. Connect to BCM using the per-node certificate
4. Start monitoring hardware and applying node labels

### Verification

```bash
# Check DaemonSet status
kubectl get daemonset -n bcm-agent
kubectl get pods -n bcm-agent

# View cm-lite-daemon logs
kubectl logs -n bcm-agent -l app.kubernetes.io/name=bcm-agent -c bcm-agent | grep cm-lite

# View K8s labeler logs
kubectl logs -n bcm-agent -l app.kubernetes.io/name=bcm-agent | grep bcm-node-labeler

# Check node labels applied
kubectl get nodes --show-labels | grep bcm.nvidia.com

# View Prometheus metrics
kubectl port-forward -n bcm-agent daemonset/bcm-agent 9100:9100
curl http://localhost:9100/metrics

# Verify WebSocket connection to BCM head node
kubectl exec -it -n bcm-agent <pod-name> -- cat /var/run/bcm-agent/cm-lite-daemon.pid
```

## Project Structure

```
bcm-agent/
├── Dockerfile                        # Container image definition
├── .dockerignore                     # Docker build exclusions
├── cm-lite-daemon/                   # NVIDIA cm-lite-daemon (official)
│   ├── cm-lite-daemon                # Main daemon executable
│   ├── cm_lite_daemon/               # Python package
│   ├── requirements.txt              # Python dependencies
│   └── service/systemd               # Systemd service unit
├── src/
│   ├── k8s_node_labeler.py           # Kubernetes integration daemon
│   ├── entrypoint.sh                 # Container entrypoint script
│   └── (reuses k8s_integration.py from src-old/)
├── scripts/
│   └── create-cert-secret.sh         # Helper to create certificate Secret
├── kubernetes/                       # Plain Kubernetes manifests
│   ├── namespace.yaml
│   ├── serviceaccount.yaml
│   ├── clusterrole.yaml
│   ├── clusterrolebinding.yaml
│   ├── configmap.yaml
│   ├── daemonset.yaml
│   ├── service.yaml
│   ├── secret-certificates.yaml      # Certificate Secret template
│   └── kustomization.yaml
├── helm/bcm-agent/                   # Helm chart
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── templates/
│   │   ├── daemonset.yaml
│   │   ├── serviceaccount.yaml
│   │   ├── clusterrole.yaml
│   │   ├── clusterrolebinding.yaml
│   │   ├── service.yaml
│   │   └── secret.yaml               # Optional Secret from values
│   └── README.md
├── src-old/                          # Previous nvnodehealth implementation (archived)
├── nvnodehealth-old/                 # NVIDIA nvnodehealth (archived)
├── BCM_AGENT_RESEARCH.md             # Research findings
├── ARCHITECTURE_DECISION.md          # Design decisions
├── IMPLEMENTATION_SUMMARY.md         # First implementation summary
├── GETTING_STARTED.md                # Deployment guide (old)
└── README.md                         # This file
```

## Features

### BCM Integration via cm-lite-daemon

The cm-lite-daemon component provides:

- **Hardware Inventory Sync** - GPUs, CPUs, memory, network adapters
- **Real-time Status Updates** - Node health and availability
- **Firmware Information** - Current versions for upgrade planning
- **Two-way Communication** - Receives configuration updates from BCM
- **Certificate-based Authentication** - Secure TLS connection to BCM head node
- **Automatic Reconnection** - Handles network disruptions gracefully

### Hardware Monitoring

cm-lite-daemon collects and reports:
- **GPU Information** - Model, memory, driver version, utilization
- **CPU Details** - Model, core count, speed
- **Memory** - Total, available, usage
- **Network Interfaces** - InfiniBand, Ethernet status
- **BMC Sensors** - Temperature, power, fans (via IPMI)
- **Storage** - Disk types, capacity, health

### Node Labeling

The K8s Node Labeler component reads data from cm-lite-daemon and applies labels:

```
bcm.nvidia.com/node-name: node001
bcm.nvidia.com/bcm-cluster: bcmhead
bcm.nvidia.com/gpu-count: 8
bcm.nvidia.com/cpu-model: AMD-EPYC-7763
bcm.nvidia.com/memory-gb: 512
bcm.nvidia.com/health-status: healthy
```

Use in pod specs for intelligent scheduling:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-workload
spec:
  nodeSelector:
    bcm.nvidia.com/gpu-count: "8"
    bcm.nvidia.com/health-status: "healthy"
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: bcm.nvidia.com/bcm-cluster
            operator: In
            values:
            - bcmhead
```

### Prometheus Metrics

Exported on port 9100 (configurable):

- `bcm_node_info` - Node information (node name, BCM cluster)
- `bcm_hardware_health` - Hardware health status by component
- `bcm_gpu_count` - Number of GPUs detected
- `bcm_cpu_count` - Number of CPUs
- `bcm_memory_gb` - Total memory in GB
- `bcm_last_sync_timestamp` - Last BCM sync timestamp

## Configuration

### Helm Values

Key configuration options in `values.yaml`:

```yaml
config:
  # BCM head node
  bcm:
    host: "master"              # BCM head node hostname/IP
    port: 8081                  # cmdaemon port
    configFile: ""              # Optional: path to config.json

  # Kubernetes integration
  kubernetes:
    syncInterval: 300           # Label sync interval (seconds)
    labelPrefix: "bcm.nvidia.com"
    enableLabeling: true
    disableLabeling: false      # Metrics-only mode

  # Certificates (mounted from Secret)
  certificates:
    certFile: "/etc/bcm-agent/certs/cert.pem"
    keyFile: "/etc/bcm-agent/certs/cert.key"
    caFile: "/etc/bcm-agent/certs/cacert.pem"

  # Logging
  debug: false
  logLevel: "info"

# Certificate Secret
certificates:
  secretName: "bcm-agent-certs"
  create: false                 # Manage certificates externally

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

tolerations:
  - operator: Exists            # Run on all nodes
```

### Environment Variables

Set automatically by Helm, can be overridden:

**BCM Connection:**
- `BCM_HOST` - BCM head node hostname/IP (default: master)
- `BCM_PORT` - cmdaemon port (default: 8081)
- `CERT_FILE` - Path to client certificate
- `KEY_FILE` - Path to client private key
- `CA_FILE` - Path to CA certificate
- `CONFIG_FILE` - Optional path to cm-lite-daemon config.json

**Kubernetes Integration:**
- `NODE_NAME` - Node name (set via downward API)
- `SYNC_INTERVAL` - Label sync interval in seconds (default: 300)
- `LABEL_PREFIX` - Kubernetes label prefix (default: bcm.nvidia.com)
- `ENABLE_LABELING` - Enable node labeling (default: true)
- `DISABLE_LABELING` - Disable labeling, metrics only (default: false)

**Monitoring:**
- `METRICS_PORT` - Prometheus metrics port (default: 9100)

**Logging:**
- `LOG_LEVEL` - debug, info, warning, error (default: info)
- `DEBUG` - Enable debug mode (default: false)

## Building

### Prerequisites

⚠️ **IMPORTANT**: This container image requires NVIDIA's proprietary `cm-lite-daemon` which is NOT included in this repository.

You must build the container image on a system with access to your NVIDIA Base Command Manager installation.

### Build Container Image

**Build on BCM Head Node (Recommended):**

```bash
# On BCM head node (e.g., 192.168.122.204)
cd /path/to/nvidia-bcm-lite-daemon

# Copy NVIDIA cm-lite-daemon zip to build context
cp /cm/shared/apps/cm-lite-daemon-dist/cm-lite-daemon.zip .

# Build with Podman
podman build -t bcm-agent:latest .

# Clean up
rm cm-lite-daemon.zip

# Tag for your registry
podman tag bcm-agent:latest quay.io/your-org/bcm-agent:1.0.0

# Push to registry
podman push quay.io/your-org/bcm-agent:1.0.0
```

**Push to OpenShift Internal Registry:**

```bash
# On BCM head node with OpenShift access
cd /path/to/nvidia-bcm-lite-daemon

# Copy NVIDIA cm-lite-daemon zip
cp /cm/shared/apps/cm-lite-daemon-dist/cm-lite-daemon.zip .

# Build
podman build -t bcm-agent:latest .

# Tag for OpenShift internal registry
podman tag bcm-agent:latest image-registry.openshift-image-registry.svc:5000/default/bcm-agent:latest

# Push to OpenShift (requires authentication)
podman push image-registry.openshift-image-registry.svc:5000/default/bcm-agent:latest

# Clean up
rm cm-lite-daemon.zip
```

**Note:** The resulting container image contains NVIDIA proprietary software and should NOT be redistributed publicly. Keep it within your internal registry.

### Test Locally

```bash
# Prepare certificates for testing
mkdir -p /tmp/bcm-certs
cp /cm/local/apps/cm-lite-daemon/etc/*.pem /tmp/bcm-certs/

# Run container locally (requires privileged access and BCM connectivity)
podman run --rm -it \
  --privileged \
  --net=host \
  --pid=host \
  -v /dev:/dev \
  -v /sys:/sys \
  -v /proc:/host/proc:ro \
  -v /tmp/bcm-certs:/etc/bcm-agent/certs:ro \
  -e NODE_NAME=$(hostname) \
  -e BCM_HOST=bcmhead \
  -e BCM_PORT=8081 \
  -e SYNC_INTERVAL=60 \
  -e DEBUG=true \
  bcm-agent:latest
```

## Deployment Options

### For Kubernetes/OpenShift Clusters

#### Option 1: Helm (Recommended)

```bash
helm install bcm-agent ./helm/bcm-agent \
  --namespace bcm-agent \
  --create-namespace
```

#### Option 2: Kustomize

```bash
kubectl apply -k kubernetes/
```

#### Option 3: Plain Manifests

```bash
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -f kubernetes/serviceaccount.yaml
kubectl apply -f kubernetes/clusterrole.yaml
kubectl apply -f kubernetes/clusterrolebinding.yaml
kubectl apply -f kubernetes/configmap.yaml
kubectl apply -f kubernetes/daemonset.yaml
kubectl apply -f kubernetes/service.yaml
```

### For Standalone RHEL Servers

#### Option 4: Ansible Role (Recommended for RHEL)

Deploy BCM Agent on standalone RHEL servers using the `nvidia.bcm.bcm_agent` Ansible role:

```bash
# Install the collection
ansible-galaxy collection install nvidia.bcm

# Create inventory
cat > inventory.yml << EOF
all:
  hosts:
    bcmhead:
      ansible_host: 10.141.255.254
    node001:
      ansible_host: 10.141.160.1
  vars:
    bcm_agent_bcm_host: "bcmhead"
    bcm_agent_image_tag: "1.0.0"
EOF

# Deploy with Ansible
ansible-playbook -i inventory.yml \
  nvidia.bcm.playbooks.deploy-bcm-agent
```

See [Ansible Role Documentation](../ansible_collections/nvidia/bcm/roles/bcm_agent/README.md) for details.

#### Option 5: Manual Quadlet Deployment

For manual deployment on a single RHEL server, see [Quadlet README](quadlet/README.md).

## Comparison with Alternatives

| Approach | Use Case | Deployment | Privileges |
|----------|----------|------------|------------|
| **BCM Agent DaemonSet** | Monitoring + labeling | Helm/DaemonSet | Privileged (hardware access) |
| **ocp-nvidia-bcm** | Full BCM node management | MachineConfig | Very privileged (full cmdaemon) |
| **Manual nvnodehealth** | One-time checks | SSH/manual | Root |

BCM Agent is designed for **monitoring and metadata sync**, not full BCM management.

## Integration with BCM

This agent **complements** BCM head node:

1. **BCM provisions bare metal** - PXE boot, OS installation, inventory
2. **OpenShift deployed** - Via BCM automation or Assisted Installer
3. **BCM Agent monitors** - Hardware health, applies labels
4. **Metadata sync** - (Future) Report status back to BCM head node

The agent does NOT replace BCM - it extends monitoring to OpenShift.

## Troubleshooting

### Agent not running

```bash
# Check DaemonSet status
kubectl get daemonset -n bcm-agent
kubectl get pods -n bcm-agent

# View events
kubectl get events -n bcm-agent --sort-by='.lastTimestamp'

# Check for image pull errors
kubectl describe pod -n bcm-agent <pod-name>
```

### cm-lite-daemon cannot connect to BCM

```bash
# View cm-lite-daemon logs
kubectl logs -n bcm-agent <pod-name> | grep cm-lite

# Check certificate Secret
kubectl get secret bcm-agent-certs -n bcm-agent
kubectl describe secret bcm-agent-certs -n bcm-agent

# Verify network connectivity from pod to BCM head node
kubectl exec -it -n bcm-agent <pod-name> -- ping -c 3 bcmhead
kubectl exec -it -n bcm-agent <pod-name> -- telnet bcmhead 8081

# Check certificate files in pod
kubectl exec -it -n bcm-agent <pod-name> -- ls -l /etc/bcm-agent/certs/

# View full cm-lite-daemon log
kubectl exec -it -n bcm-agent <pod-name> -- cat /var/log/bcm-agent/cm-lite-daemon.log
```

### Labels not applied

```bash
# Check RBAC permissions
kubectl auth can-i patch nodes \
  --as=system:serviceaccount:bcm-agent:bcm-agent

# View current labels
kubectl get nodes --show-labels | grep bcm.nvidia.com

# Check K8s node labeler logs
kubectl logs -n bcm-agent <pod-name> | grep bcm-node-labeler

# Check for errors
kubectl logs -n bcm-agent <pod-name> | grep -i "error\|failed\|exception"
```

### Certificate Issues

```bash
# Verify certificate Secret exists
kubectl get secret bcm-agent-certs -n bcm-agent

# Check certificate content (should show base64 data)
kubectl get secret bcm-agent-certs -n bcm-agent -o yaml

# Recreate certificate Secret if needed
kubectl delete secret bcm-agent-certs -n bcm-agent
./scripts/create-cert-secret.sh /cm/local/apps/cm-lite-daemon/etc bcm-agent

# Restart pods to pick up new certificates
kubectl rollout restart daemonset/bcm-agent -n bcm-agent
```

### Debugging Inside Container

```bash
# Exec into running pod
kubectl exec -it -n bcm-agent <pod-name> -- /bin/bash

# Check cm-lite-daemon process
ps aux | grep cm-lite-daemon
cat /var/run/bcm-agent/cm-lite-daemon.pid

# Check logs
tail -f /var/log/bcm-agent/cm-lite-daemon.log

# Test BCM connectivity
ping bcmhead
telnet bcmhead 8081

# Verify certificates
ls -l /etc/bcm-agent/certs/
openssl x509 -in /etc/bcm-agent/certs/cert.pem -text -noout
```

## Contributing

This project integrates NVIDIA's official cm-lite-daemon with OpenShift. Future enhancements:

- [ ] Complete BCM data integration (read cm-lite-daemon state)
- [ ] Enhanced node labels from BCM inventory
- [ ] Firmware version tracking and upgrade coordination
- [ ] GPU utilization metrics (DCGM integration)
- [ ] Health status from BCM monitoring
- [ ] Custom Prometheus alerting rules
- [ ] Grafana dashboards for BCM metrics
- [ ] ConfigMap-based BCM configuration

## License

SPDX-FileCopyrightText: Copyright 2025 Fabien Dupont <fdupont@redhat.com>

SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

**Note:** This project uses NVIDIA's proprietary cm-lite-daemon, which must be
obtained from your NVIDIA Base Command Manager installation. See the NOTICE file
for complete licensing information.

## Related Projects

- **cm-lite-daemon** - NVIDIA's official lightweight BCM daemon for compute nodes
- **BCM (Base Command Manager)** - NVIDIA's bare metal cluster management platform
- **ocp-nvidia-bcm** - Alternative approach running full cmdaemon via MachineConfig
- **nvnodehealth** - NVIDIA's hardware health checker (archived in this project)

## Comparison with Alternatives

| Approach | Component | Deployment | BCM Sync | Use Case |
|----------|-----------|------------|----------|----------|
| **BCM Agent (this project)** | cm-lite-daemon | Helm/DaemonSet | ✅ Two-way | Monitoring + inventory sync |
| **ocp-nvidia-bcm** | Full cmdaemon | MachineConfig | ✅ Full | Complete BCM node management |
| **Manual monitoring** | nvnodehealth | SSH/cron | ❌ None | One-time health checks |

BCM Agent is designed for **monitoring and metadata sync** without full node management overhead.

---

**Questions?** See:
- `ARCHITECTURE_DECISION.md` - Design rationale
- `BCM_AGENT_RESEARCH.md` - Research findings
- `IMPLEMENTATION_SUMMARY.md` - First implementation (archived)
