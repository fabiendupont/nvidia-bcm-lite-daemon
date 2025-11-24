# BCM Agent Deployment via Quadlet (RHEL)

This guide explains how to deploy BCM Agent as a systemd service on RHEL 9+ using Podman Quadlet.

## What is Quadlet?

Quadlet is a feature in Podman 4.4+ that allows you to run containers as systemd services using simple configuration files. It's perfect for running the BCM Agent on standalone RHEL servers or BCM compute nodes.

## Prerequisites

- **RHEL 9.0+** (or compatible)
- **Podman 4.4+** (includes Quadlet support)
- **BCM head node** accessible on the network
- **BCM certificates** for cm-lite-daemon authentication

Check Podman version:
```bash
podman --version
# Should be 4.4 or higher
```

## Installation Steps

### Step 1: Prepare Certificates

Copy BCM certificates to the system:

```bash
# Create certificate directory
sudo mkdir -p /etc/bcm-agent/certs
sudo chmod 755 /etc/bcm-agent

# Copy certificates from BCM
sudo cp /cm/local/apps/cm-lite-daemon/etc/cacert.pem /etc/bcm-agent/certs/
sudo cp /cm/local/apps/cm-lite-daemon/etc/cert.pem /etc/bcm-agent/certs/
sudo cp /cm/local/apps/cm-lite-daemon/etc/cert.key /etc/bcm-agent/certs/

# Set proper permissions
sudo chmod 400 /etc/bcm-agent/certs/cert.key
sudo chmod 444 /etc/bcm-agent/certs/*.pem
sudo chown -R root:root /etc/bcm-agent/certs
```

**Note**: If deploying on a BCM-managed node, certificates may already exist in `/cm/local/apps/cm-lite-daemon/etc/`. You can create symlinks instead:

```bash
sudo mkdir -p /etc/bcm-agent/certs
sudo ln -s /cm/local/apps/cm-lite-daemon/etc/cacert.pem /etc/bcm-agent/certs/cacert.pem
sudo ln -s /cm/local/apps/cm-lite-daemon/etc/cert.pem /etc/bcm-agent/certs/cert.pem
sudo ln -s /cm/local/apps/cm-lite-daemon/etc/cert.key /etc/bcm-agent/certs/cert.key
```

### Step 2: Build or Obtain Container Image

⚠️ **IMPORTANT**: Container images must be built on the BCM head node with access to NVIDIA's cm-lite-daemon.

**Option A: Build locally on BCM head node:**

```bash
# On BCM head node
cd /path/to/nvidia-bcm-lite-daemon
./scripts/build-image.sh --tag 1.0.0

# Image is now available locally as bcm-agent:1.0.0
```

**Option B: Build and push to private registry, then pull:**

```bash
# On BCM head node - build and push
cd /path/to/nvidia-bcm-lite-daemon
./scripts/build-image.sh \
  --registry registry.example.com \
  --tag 1.0.0 \
  --push

# On target RHEL system - pull
sudo podman pull registry.example.com/bcm-agent:1.0.0
```

**Option C: Transfer image file:**

```bash
# On BCM head node - build and save
cd /path/to/nvidia-bcm-lite-daemon
./scripts/build-image.sh --tag 1.0.0
podman save bcm-agent:1.0.0 -o /tmp/bcm-agent-1.0.0.tar

# Transfer to target system
scp /tmp/bcm-agent-1.0.0.tar target-rhel-system:/tmp/

# On target system - load
sudo podman load -i /tmp/bcm-agent-1.0.0.tar
```

### Step 3: Deploy Quadlet Configuration

```bash
# Copy Quadlet file to systemd directory
sudo cp bcm-agent.container /etc/containers/systemd/

# Customize configuration if needed
sudo vi /etc/containers/systemd/bcm-agent.container
# Update BCM_HOST, image tag, etc.

# Create log directory
sudo mkdir -p /var/log/bcm-agent
sudo chmod 755 /var/log/bcm-agent
```

### Step 4: Enable and Start Service

```bash
# Reload systemd to process Quadlet file
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable bcm-agent.service

# Start the service
sudo systemctl start bcm-agent.service

# Check status
sudo systemctl status bcm-agent.service
```

## Verification

### Check Service Status

```bash
# View service status
systemctl status bcm-agent.service

# View logs
journalctl -u bcm-agent.service -f

# Check container is running
podman ps | grep bcm-agent
```

### Verify BCM Connection

```bash
# Check cm-lite-daemon logs
sudo tail -f /var/log/bcm-agent/cm-lite-daemon.log

# Check if cm-lite-daemon is connected
podman exec bcm-agent cat /var/run/bcm-agent/cm-lite-daemon.pid
podman exec bcm-agent ps aux | grep cm-lite-daemon
```

### Test Prometheus Metrics

```bash
# Metrics should be exposed on port 9100
curl http://localhost:9100/metrics

# Should see bcm_* metrics
curl -s http://localhost:9100/metrics | grep bcm_
```

## Configuration

### Environment Variables

Edit `/etc/containers/systemd/bcm-agent.container` to customize:

```ini
# BCM head node
Environment=BCM_HOST=bcmhead
Environment=BCM_PORT=8081

# Sync interval (seconds)
Environment=SYNC_INTERVAL=300

# Logging
Environment=LOG_LEVEL=info
Environment=DEBUG=false

# Metrics port
Environment=METRICS_PORT=9100
```

After changes:
```bash
sudo systemctl daemon-reload
sudo systemctl restart bcm-agent.service
```

### Resource Limits

Adjust in the `[Service]` section:

```ini
MemoryHigh=488M
MemoryMax=512M
TasksMax=128
```

### Image Updates

To update to a new image version:

```bash
# Build new version on BCM head node
cd /path/to/nvidia-bcm-lite-daemon
./scripts/build-image.sh --tag 1.0.1

# Transfer to target system (if not building locally)
podman save bcm-agent:1.0.1 -o /tmp/bcm-agent-1.0.1.tar
scp /tmp/bcm-agent-1.0.1.tar target-system:/tmp/
ssh target-system "sudo podman load -i /tmp/bcm-agent-1.0.1.tar"

# Update Quadlet file with new tag
sudo vi /etc/containers/systemd/bcm-agent.container
# Change: Image=bcm-agent:1.0.1
# Or: Image=registry.example.com/bcm-agent:1.0.1

# Restart service
sudo systemctl daemon-reload
sudo systemctl restart bcm-agent.service
```

Or enable automatic updates (pulls latest on restart):

```ini
AutoUpdate=registry
```

Then enable Podman auto-update timer:
```bash
sudo systemctl enable --now podman-auto-update.timer
```

## Troubleshooting

### Service won't start

```bash
# Check systemd unit file generated by Quadlet
systemctl cat bcm-agent.service

# View detailed status
systemctl status bcm-agent.service -l

# Check container logs
podman logs bcm-agent

# Check for SELinux denials
sudo ausearch -m avc -ts recent | grep bcm-agent
```

### Certificate errors

```bash
# Verify certificates exist
ls -l /etc/bcm-agent/certs/

# Check permissions
stat /etc/bcm-agent/certs/cert.key

# Test certificate validity
openssl x509 -in /etc/bcm-agent/certs/cert.pem -text -noout
```

### Cannot connect to BCM

```bash
# Test network connectivity from container
podman exec bcm-agent ping -c 3 bcmhead
podman exec bcm-agent nc -zv bcmhead 8081

# Check from host
ping -c 3 bcmhead
nc -zv bcmhead 8081

# View cm-lite-daemon logs
sudo tail -100 /var/log/bcm-agent/cm-lite-daemon.log
```

### SELinux issues

If SELinux blocks volume mounts:

```bash
# Relabel directories
sudo restorecon -Rv /etc/bcm-agent
sudo restorecon -Rv /var/log/bcm-agent

# Or temporarily set to permissive for testing
sudo setenforce 0
# Check if service starts, then fix SELinux policy
sudo setenforce 1
```

## Management Commands

```bash
# Start service
sudo systemctl start bcm-agent.service

# Stop service
sudo systemctl stop bcm-agent.service

# Restart service
sudo systemctl restart bcm-agent.service

# View status
sudo systemctl status bcm-agent.service

# View logs (follow)
journalctl -u bcm-agent.service -f

# View logs (last 100 lines)
journalctl -u bcm-agent.service -n 100

# Disable service
sudo systemctl disable bcm-agent.service

# Remove service
sudo systemctl stop bcm-agent.service
sudo systemctl disable bcm-agent.service
sudo rm /etc/containers/systemd/bcm-agent.container
sudo systemctl daemon-reload
```

## Comparison: Quadlet vs Kubernetes

| Feature | Quadlet (RHEL) | Kubernetes/OpenShift |
|---------|----------------|---------------------|
| **Deployment** | Single systemd unit file | Helm chart + manifests |
| **Scheduling** | Manual per-host | Automatic DaemonSet |
| **Node Labels** | N/A (no K8s API) | ✅ Automatic labeling |
| **HA** | Single node | Multi-node cluster |
| **Management** | systemctl commands | kubectl commands |
| **Use Case** | Standalone servers | Cluster deployments |

## Integration with Kubernetes Deployment

You can run BCM Agent in both modes:

1. **Quadlet on BCM head node** - Monitor the head node itself
2. **DaemonSet on OpenShift cluster** - Monitor cluster compute nodes

Both instances connect to the same BCM head node via cm-lite-daemon.

## Next Steps

- Monitor BCM head node for new nodes registered via cm-lite-daemon
- Integrate Prometheus metrics with existing monitoring (Grafana, etc.)
- Set up alerting for connection failures
- Plan firmware updates coordinated via BCM

## Additional Resources

- [Podman Quadlet Documentation](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
- [BCM Agent Main README](../README.md)
- [BCM Documentation](https://docs.nvidia.com/base-command-manager/)
