# BCM Agent Helm Chart

NVIDIA BCM Agent for OpenShift - Hardware monitoring and node labeling using nvnodehealth.

## TL;DR

```bash
helm install bcm-agent ./helm/bcm-agent --namespace bcm-agent --create-namespace
```

## Introduction

This Helm chart deploys the BCM Agent as a DaemonSet on OpenShift/Kubernetes. The agent:

- Runs NVIDIA nvnodehealth periodically to check hardware health
- Applies node labels based on hardware inventory
- Exports Prometheus metrics for monitoring
- Integrates with OpenShift monitoring stack

## Prerequisites

- Kubernetes 1.24+ / OpenShift 4.12+
- Helm 3.0+
- Nodes with hardware to monitor (GPUs, InfiniBand, etc.)
- Privileged containers allowed (required for hardware access)

## Installation

### Install with required image configuration

⚠️ **IMPORTANT**: You must specify your own container registry. No public image exists.

```bash
# Install to custom namespace with your registry
helm install bcm-agent ./helm/bcm-agent \
  --namespace bcm-monitoring \
  --create-namespace \
  --set image.repository=registry.example.com/bcm-agent \
  --set image.tag=1.0.0
```

### Install to default namespace (for testing)

```bash
helm install bcm-agent ./helm/bcm-agent \
  --namespace default \
  --set image.repository=your-registry/bcm-agent \
  --set image.tag=latest
```

### Install with custom values

```bash
helm install bcm-agent ./helm/bcm-agent \
  --namespace bcm-agent \
  --create-namespace \
  --set image.repository=registry.example.com/bcm-agent \
  --set image.tag=1.0.0 \
  --set config.checkInterval=600 \
  --set config.labelPrefix="my-bcm.nvidia.com" \
  --set metrics.port=9100
```

### Install with values file

```bash
helm install bcm-agent ./helm/bcm-agent \
  --namespace bcm-agent \
  --create-namespace \
  --values my-values.yaml
```

## Configuration

The following table lists the configurable parameters of the BCM Agent chart and their default values.

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.repository` | Image repository (⚠️ **REQUIRED**: Change to your registry) | `registry.example.com/bcm-agent` |
| `image.tag` | Image tag | `latest` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `config.checkInterval` | Health check interval (seconds) | `300` |
| `config.labelPrefix` | Kubernetes label prefix | `bcm.nvidia.com` |
| `config.enableLabeling` | Enable node labeling | `true` |
| `config.healthGroups` | Health check groups to run | `""` (all) |
| `config.logLevel` | Log level | `info` |
| `metrics.enabled` | Enable Prometheus metrics | `true` |
| `metrics.port` | Metrics port | `9100` |
| `resources.requests.memory` | Memory request | `256Mi` |
| `resources.requests.cpu` | CPU request | `100m` |
| `resources.limits.memory` | Memory limit | `512Mi` |
| `resources.limits.cpu` | CPU limit | `500m` |
| `nodeSelector` | Node selector | `{}` |
| `tolerations` | Tolerations | `[{operator: Exists}]` |
| `priorityClassName` | Priority class name | `system-node-critical` |

## Upgrading

```bash
helm upgrade bcm-agent ./helm/bcm-agent \
  --namespace bcm-agent \
  --values my-values.yaml
```

## Uninstalling

```bash
helm uninstall bcm-agent --namespace bcm-agent
```

## Monitoring

The agent exposes Prometheus metrics on port 9100 (configurable). Metrics include:

- `bcm_agent_health_status` - Node health status (1=healthy, 0=unhealthy)
- `bcm_agent_checks_total` - Total health checks performed
- `bcm_agent_checks_ok` - Number of OK checks
- `bcm_agent_checks_failed` - Number of failed checks
- `bcm_agent_gpu_count` - Number of GPUs detected

### Prometheus ServiceMonitor (Optional)

If using Prometheus Operator, create a ServiceMonitor:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: bcm-agent
  namespace: bcm-agent
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: bcm-agent
  endpoints:
    - port: metrics
      interval: 60s
```

## Node Labels

The agent applies labels to nodes in the format `<prefix>/<key>`. Default labels:

- `bcm.nvidia.com/health-status` - healthy | unhealthy
- `bcm.nvidia.com/checks-ok` - Number of passing checks
- `bcm.nvidia.com/checks-failed` - Number of failing checks
- `bcm.nvidia.com/gpu-present` - true | false
- `bcm.nvidia.com/gpu-count` - Number of GPUs

## Troubleshooting

### Check agent logs

```bash
kubectl logs -n bcm-agent -l app.kubernetes.io/name=bcm-agent --tail=100 -f
```

### Check node labels

```bash
kubectl get nodes --show-labels | grep bcm.nvidia.com
```

### Verify metrics

```bash
kubectl port-forward -n bcm-agent daemonset/bcm-agent 9100:9100
curl http://localhost:9100/metrics
```

### Check RBAC permissions

```bash
kubectl auth can-i patch nodes --as=system:serviceaccount:bcm-agent:bcm-agent
```

## License

SPDX-FileCopyrightText: Copyright 2025 Fabien Dupont <fdupont@redhat.com>

SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the repository root for details.

This project uses NVIDIA's proprietary cm-lite-daemon. See the NOTICE file
for complete licensing information.
