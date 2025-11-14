# BCM Agent for OpenShift - Architecture Decision

**Date:** 2025-11-05

## Context

We discovered three different approaches for BCM integration with OpenShift:

1. **Our initial plan**: Custom BCM Agent DaemonSet using nvnodehealth
2. **NVIDIA's nvnodehealth**: Official hardware health checker (one-shot tool)
3. **ocp-nvidia-bcm**: Runs full cmdaemon on nodes via MachineConfig

## Analysis of Existing Solution (ocp-nvidia-bcm)

### What it does:
- Runs **full cmdaemon** on each OpenShift node
- Uses **MachineConfig** to deploy via systemd service
- Container runs with: `--privileged --net=host --ipc=host --pid=host`
- Mounts certificates for BCM cluster communication
- Requires NFS mount to `/cm/shared`

### Architecture:
```yaml
MachineConfig (99-master-cmd)
  └─> systemd unit (cmd.service)
       └─> podman run quay.io/rh-ee-eelgaev/nvidia-cmd:latest
            └─> cmdaemon (full BCM node daemon)
```

### Known Gaps (from their docs):
- SSH root login required (disabled by default in RHCOS)
- Slurm must be installed and running
- Requires `/cm/shared` NFS mount
- Requires ntpd/chronyd

## Comparison Matrix

| Approach | Component | Privileges | Deployment | Use Case |
|----------|-----------|------------|------------|----------|
| **ocp-nvidia-bcm** | Full cmdaemon | Privileged, host networking | MachineConfig | Full BCM node management |
| **nvnodehealth** | Health checker only | Privileged (for IPMI/GPU) | DaemonSet/MachineConfig | Hardware monitoring |
| **Custom Agent** | Wrapper + nvnodehealth | Privileged (for health checks) | DaemonSet + Helm | Monitoring + K8s integration |

## Proposed Hybrid Approach

### Option A: DaemonSet with nvnodehealth (Recommended)

**Purpose:** Monitoring and node labeling only (NOT full BCM management)

**Components:**
1. **nvnodehealth** - NVIDIA's official health checker
2. **Wrapper daemon** - Runs nvnodehealth periodically
3. **K8s integration** - Applies node labels, exports Prometheus metrics
4. **Helm chart** - Easy deployment and configuration

**Deployment:**
```
Helm Chart
  └─> DaemonSet
       └─> Pod (per node)
            ├─> Init: Run initial health check
            └─> Main: Wrapper daemon
                 ├─> Runs nvnodehealth every N minutes
                 ├─> Parses results
                 ├─> Updates node labels
                 └─> Exports Prometheus metrics
```

**Advantages:**
- ✅ Standard Kubernetes deployment (no MachineConfig needed)
- ✅ Uses official NVIDIA nvnodehealth
- ✅ Easy to install/uninstall via Helm
- ✅ Node labeling for hardware-aware scheduling
- ✅ Prometheus metrics for OpenShift monitoring
- ✅ No NFS or SSH requirements
- ✅ Works alongside BCM head node for provisioning

**Disadvantages:**
- ❌ NOT a full BCM node agent (cmdaemon)
- ❌ Cannot provision/manage nodes from BCM
- ❌ One-way sync (cluster → BCM metadata)

### Option B: MachineConfig with cmdaemon (Full BCM Integration)

**Purpose:** Full BCM node management on OpenShift

**Uses:** ocp-nvidia-bcm approach

**Advantages:**
- ✅ Full BCM node capabilities
- ✅ Two-way BCM ↔ OpenShift integration
- ✅ BCM can manage nodes directly

**Disadvantages:**
- ❌ Requires MachineConfig (node reboot)
- ❌ Requires NFS, SSH, Slurm
- ❌ Complex setup
- ❌ Conflicts with OpenShift's node management
- ❌ Very privileged (full host access)

## Decision

### For Our Use Case: **Option A - DaemonSet with nvnodehealth**

**Rationale:**

Based on the original requirements:
> "We would mostly need BCM Agent for Monitoring, possibly labelling nodes via Node Feature Discovery.
> The OpenShift cluster would be deployed separately, via BCM custom automation, and the agent would close the loop."

This matches **Option A** perfectly:
- BCM provisions bare metal (via our existing automation)
- OpenShift deployed on BCM-managed nodes
- **BCM Agent DaemonSet** provides:
  - Hardware health monitoring
  - Node labeling for scheduling
  - Metrics for OpenShift monitoring
  - Inventory sync back to BCM

We do **NOT need**:
- Full cmdaemon on nodes
- BCM to SSH into nodes
- NFS mounts
- Complex MachineConfig setup

## Implementation Plan

### Phase 1: Core Agent (Week 1)
1. ✅ Use NVIDIA's nvnodehealth as-is
2. Create wrapper daemon script:
   ```python
   while True:
       results = run_nvnodehealth()
       parse_results(results)
       update_node_labels(results)
       export_prometheus_metrics(results)
       sleep(interval)
   ```
3. Create Dockerfile (based on nvnodehealth's)
4. Build and test container locally

### Phase 2: Kubernetes Integration (Week 1-2)
1. Create K8s manifests:
   - ServiceAccount
   - ClusterRole/ClusterRoleBinding (for node labeling)
   - DaemonSet
   - ConfigMap (for configuration)
2. Add Prometheus metrics endpoint
3. Test on single node

### Phase 3: Helm Chart (Week 2)
1. Create Helm chart structure
2. Parameterize:
   - Check interval
   - Label prefix
   - Health check groups
   - Resource limits
3. Add values.yaml with sensible defaults
4. Test installation

### Phase 4: BCM Sync (Week 2-3)
1. Optional: Add BCM PythonCM integration
2. Report health status back to BCM
3. Sync firmware versions
4. Test with BCM head node

### Phase 5: Production Hardening (Week 3-4)
1. Security: Non-root user where possible
2. Resource limits
3. Monitoring dashboards
4. Documentation
5. CI/CD pipeline

## Files to Create

```
bcm-agent/
├── nvnodehealth/                    # Copy of NVIDIA nvnodehealth
│   ├── Dockerfile                   # Original NVIDIA Dockerfile
│   └── ... (all nvnodehealth files)
├── src/
│   ├── wrapper_daemon.py            # Main daemon loop
│   ├── k8s_integration.py           # Node labeling, etc.
│   ├── prometheus_exporter.py       # Metrics export
│   ├── bcm_sync.py                  # Optional: sync to BCM
│   └── requirements.txt
├── Dockerfile                       # Our wrapper + nvnodehealth
├── helm/
│   └── bcm-agent/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── templates/
│       │   ├── daemonset.yaml
│       │   ├── serviceaccount.yaml
│       │   ├── clusterrole.yaml
│       │   ├── clusterrolebinding.yaml
│       │   ├── configmap.yaml
│       │   └── service.yaml       # For Prometheus metrics
│       └── README.md
├── docs/
│   ├── INSTALLATION.md
│   ├── CONFIGURATION.md
│   └── TROUBLESHOOTING.md
└── README.md
```

## Relationship with ocp-nvidia-bcm

Their project solves a **different problem**:
- **ocp-nvidia-bcm**: Run full BCM management on OpenShift nodes
- **Our project**: Monitor OpenShift nodes with BCM integration

These are **complementary**, not competing approaches.

## Next Steps

1. Approve this architecture decision
2. Copy nvnodehealth to project
3. Create wrapper daemon
4. Build Dockerfile
5. Create DaemonSet manifest
6. Create Helm chart

---

**Decision Approved By:** [TBD]
**Date:** [TBD]
