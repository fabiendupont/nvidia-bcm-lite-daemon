# BCM Agent Documentation

Comprehensive documentation for deploying and managing the BCM Agent on Kubernetes and OpenShift.

## Quick Navigation

### Getting Started
- **[Kubernetes Deployment Guide](KUBERNETES_DEPLOYMENT.md)** - Complete deployment guide for Kubernetes/OpenShift
- **[Bootstrap Certificate Setup](BOOTSTRAP_CERTIFICATES.md)** - Set up bootstrap certificates for auto-provisioning
- **[Main README](../README.md)** - Project overview and quick start

### Operations
- **[Certificate Management](CERTIFICATE_MANAGEMENT.md)** - Certificate lifecycle, rotation, and monitoring
- **[Helm Chart README](../helm/bcm-agent/README.md)** - Helm chart configuration reference

### Architecture & Design
- **[Architecture Decision](../ARCHITECTURE_DECISION.md)** - Design decisions and rationale
- **[Implementation Summary](../IMPLEMENTATION_SUMMARY.md)** - Implementation details

## Documentation Overview

### For New Users

1. Start with the [Main README](../README.md) to understand what BCM Agent does
2. Follow the [Kubernetes Deployment Guide](KUBERNETES_DEPLOYMENT.md) to deploy
3. Set up [Bootstrap Certificates](BOOTSTRAP_CERTIFICATES.md) for automatic provisioning
4. Review [Certificate Management](CERTIFICATE_MANAGEMENT.md) for ongoing operations

### For Operators

- **Daily Operations:** [Certificate Management](CERTIFICATE_MANAGEMENT.md) - Monitoring and troubleshooting
- **Upgrades:** [Kubernetes Deployment Guide](KUBERNETES_DEPLOYMENT.md#upgrading) - Upgrade procedures
- **Troubleshooting:** Each guide includes troubleshooting sections

### For Developers

- **Architecture:** [Architecture Decision](../ARCHITECTURE_DECISION.md) - Design philosophy
- **Implementation:** [Implementation Summary](../IMPLEMENTATION_SUMMARY.md) - Technical details
- **Building:** [Main README](../README.md#building) - Build instructions

## Document Summaries

### Kubernetes Deployment Guide

**[KUBERNETES_DEPLOYMENT.md](KUBERNETES_DEPLOYMENT.md)**

Complete guide for deploying bcm-agent on Kubernetes and OpenShift:

- Prerequisites and architecture overview
- Step-by-step deployment instructions
- Configuration reference
- Upgrading and rollback procedures
- Troubleshooting common issues
- Production best practices

**Target audience:** Kubernetes administrators, DevOps engineers

### Bootstrap Certificate Setup

**[BOOTSTRAP_CERTIFICATES.md](BOOTSTRAP_CERTIFICATES.md)**

Detailed guide for setting up the bootstrap certificate pattern:

- Overview of bootstrap certificate architecture
- Creating bootstrap certificates on BCM
- Creating Kubernetes Secrets
- Verifying certificate auto-generation
- Certificate lifecycle and rotation
- Security considerations
- Advanced configurations

**Target audience:** Security administrators, Kubernetes operators

### Certificate Management

**[CERTIFICATE_MANAGEMENT.md](CERTIFICATE_MANAGEMENT.md)**

Comprehensive guide for managing BCM certificates:

- Certificate types and hierarchy
- Creating and monitoring certificates
- Certificate rotation procedures
- Revocation and troubleshooting
- Automation with CronJobs and operators
- Best practices and security

**Target audience:** Operations teams, security administrators

### Helm Chart README

**[../helm/bcm-agent/README.md](../helm/bcm-agent/README.md)**

Quick reference for the Helm chart:

- Installation instructions
- Configuration parameters
- Monitoring and metrics
- Node labels reference
- Troubleshooting

**Target audience:** Kubernetes administrators using Helm

## Common Workflows

### Initial Deployment

1. Read [Main README](../README.md) for overview
2. Build container image (see [Kubernetes Deployment Guide](KUBERNETES_DEPLOYMENT.md#1-build-container-image))
3. Create bootstrap certificate (see [Bootstrap Certificate Setup](BOOTSTRAP_CERTIFICATES.md#step-1-create-bootstrap-certificate-on-bcm))
4. Create Kubernetes Secret (see [Bootstrap Certificate Setup](BOOTSTRAP_CERTIFICATES.md#step-3-create-kubernetes-secret))
5. Deploy with Helm (see [Kubernetes Deployment Guide](KUBERNETES_DEPLOYMENT.md#3-deploy-via-helm))
6. Verify deployment (see [Kubernetes Deployment Guide](KUBERNETES_DEPLOYMENT.md#4-verify-deployment))

### Certificate Rotation

1. Check certificate expiration (see [Certificate Management](CERTIFICATE_MANAGEMENT.md#certificate-monitoring))
2. Rotate bootstrap certificate if needed (see [Certificate Management](CERTIFICATE_MANAGEMENT.md#rotating-bootstrap-certificate))
3. Rotate per-node certificates (see [Certificate Management](CERTIFICATE_MANAGEMENT.md#rotating-per-node-certificates))
4. Verify new certificates are working

### Troubleshooting Connection Issues

1. Check pod logs (see [Kubernetes Deployment Guide](KUBERNETES_DEPLOYMENT.md#troubleshooting))
2. Verify certificate validity (see [Certificate Management](CERTIFICATE_MANAGEMENT.md#troubleshooting))
3. Test network connectivity to BCM head node
4. Verify certificates are correctly mounted
5. Check BCM head node session status

### Upgrading

1. Build new container image (see [Kubernetes Deployment Guide](KUBERNETES_DEPLOYMENT.md#1-build-container-image))
2. Update Helm release (see [Kubernetes Deployment Guide](KUBERNETES_DEPLOYMENT.md#upgrading))
3. Monitor rollout status
4. Verify connectivity and functionality
5. Rollback if issues occur

## Key Concepts

### Bootstrap Certificate Pattern

The bcm-agent uses a **bootstrap certificate** approach:

- One shared bootstrap certificate in a Kubernetes Secret
- Each pod auto-generates a unique per-node certificate on first start
- Per-node certificates persist on hostPath and survive pod restarts
- Fully automatic and idempotent

**Benefits:**
- Secure (unique certificates per node)
- Scalable (no Secret size limits)
- Simple (one-time bootstrap setup)
- Automatic (no manual intervention)

See [Bootstrap Certificate Setup](BOOTSTRAP_CERTIFICATES.md) for details.

### Certificate Lifecycle

```
Bootstrap Setup (one-time)
    ↓
Per-Node Generation (automatic)
    ↓
Pod Restarts (reuse existing cert)
    ↓
Monitoring (check expiration)
    ↓
Rotation (before expiry)
```

See [Certificate Management](CERTIFICATE_MANAGEMENT.md) for lifecycle details.

### Architecture

```
BCM Head Node
    ↓ (WebSocket TLS)
Bootstrap Certificate → Per-Node Certificates
    ↓
DaemonSet Pods (one per node)
    ├─> cm-lite-daemon (BCM monitoring)
    └─> k8s_node_labeler (Kubernetes integration)
```

See [Architecture Decision](../ARCHITECTURE_DECISION.md) for design rationale.

## Support and Troubleshooting

### Documentation

- Each guide has a dedicated troubleshooting section
- Common issues are documented with solutions
- Examples include commands and expected outputs

### Logs

```bash
# View pod logs
kubectl logs -n default -l app.kubernetes.io/name=bcm-agent --tail=100

# Check certificate generation
kubectl logs -n default <pod-name> | grep -A10 "Bootstrap certificates detected"

# Monitor cm-lite-daemon connection
kubectl logs -n default <pod-name> | grep "Websocket"
```

### Verification

```bash
# Check deployment status
kubectl get daemonset bcm-agent -n default
kubectl get pods -n default -l app.kubernetes.io/name=bcm-agent

# Verify certificates
kubectl get secret bcm-bootstrap-cert -n default

# Check node labels
kubectl get nodes --show-labels | grep bcm.nvidia.com

# Test metrics
kubectl port-forward -n default daemonset/bcm-agent 9100:9100
curl http://localhost:9100/metrics
```

## Contributing

When updating documentation:

1. Keep each guide focused on a specific topic
2. Include practical examples with expected outputs
3. Add troubleshooting sections for common issues
4. Cross-reference related documentation
5. Update this index when adding new guides

## Feedback

For documentation issues:

- Check existing troubleshooting sections
- Review related guides (cross-references provided)
- Open an issue if documentation is unclear or missing information

## License

SPDX-FileCopyrightText: Copyright 2025 Fabien Dupont <fdupont@redhat.com>

SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the repository root for details.
