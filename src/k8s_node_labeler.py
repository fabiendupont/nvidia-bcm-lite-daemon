#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2025 Fabien Dupont <fdupont@redhat.com>
# SPDX-License-Identifier: Apache-2.0
"""
Kubernetes Node Labeler for BCM Agent

Reads hardware information from BCM (via cm-lite-daemon) and applies
labels to the local Kubernetes node for hardware-aware scheduling.
Also exports Prometheus metrics for monitoring.
"""

import argparse
import json
import logging
import os
import socket
import sys
import time
from typing import Dict, Optional

try:
    from prometheus_client import start_http_server, Gauge, Info
except ImportError:
    print("ERROR: prometheus_client not installed", file=sys.stderr)
    sys.exit(1)

try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
except ImportError:
    print("ERROR: kubernetes library not installed", file=sys.stderr)
    sys.exit(1)


class KubernetesClient:
    """Client for Kubernetes API operations"""

    def __init__(self, node_name: str, label_prefix: str = "bcm.nvidia.com"):
        self.label_prefix = label_prefix
        self.v1 = None
        self.node_name = node_name
        self.logger = logging.getLogger('k8s-client')

    def connect(self) -> bool:
        """Connect to Kubernetes API"""
        try:
            # Try in-cluster config first (for DaemonSet)
            config.load_incluster_config()
            self.logger.info("Loaded in-cluster Kubernetes config")
        except config.ConfigException:
            try:
                # Fall back to kubeconfig (for local testing)
                config.load_kube_config()
                self.logger.info("Loaded kubeconfig")
            except Exception as e:
                self.logger.error(f"Failed to load Kubernetes config: {e}")
                return False

        self.v1 = client.CoreV1Api()
        self.logger.info(f"Connected to Kubernetes API for node: {self.node_name}")
        return True

    def apply_labels(self, labels: Dict[str, str]) -> bool:
        """Apply labels to the node"""
        if not self.v1:
            self.logger.error("Not connected to Kubernetes API")
            return False

        # Add prefix to all labels
        prefixed_labels = {
            f"{self.label_prefix}/{k}": self._sanitize_label_value(v)
            for k, v in labels.items()
        }

        try:
            body = {"metadata": {"labels": prefixed_labels}}
            self.v1.patch_node(self.node_name, body)
            self.logger.info(f"Applied {len(prefixed_labels)} labels to node {self.node_name}")
            return True
        except ApiException as e:
            self.logger.error(f"Failed to apply labels: {e}")
            return False

    @staticmethod
    def _sanitize_label_value(value: str) -> str:
        """Sanitize label value to conform to Kubernetes requirements"""
        if not value:
            return "unknown"
        value = str(value)[:63]
        value = value.replace('/', '_').replace(' ', '-').replace(':', '-')
        value = value.strip('-_.')
        return value if value else "unknown"


class BCMNodeLabeler:
    """
    Kubernetes node labeler that integrates with BCM via cm-lite-daemon.

    Reads hardware information and applies labels to enable hardware-aware
    scheduling in OpenShift/Kubernetes.
    """

    def __init__(self, args):
        self.args = args
        self.running = True
        self.logger = self._setup_logging()
        self.node_name = self._get_node_name()

        # Kubernetes client
        self.k8s_client = None
        if not args.disable_labeling:
            try:
                self.k8s_client = KubernetesClient(
                    node_name=self.node_name,
                    label_prefix=args.label_prefix
                )
                self.k8s_client.connect()
                self.logger.info(f"Connected to Kubernetes API for node {self.node_name}")
            except Exception as e:
                self.logger.error(f"Failed to connect to Kubernetes API: {e}")
                if not args.metrics_only:
                    raise

        # Prometheus metrics
        self.metrics = self._setup_metrics()

    def _setup_logging(self) -> logging.Logger:
        """Configure logging"""
        level = logging.DEBUG if self.args.debug else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(levelname)-8s (%(asctime)s) [%(filename)s:%(lineno)d] %(message)s'
        )
        return logging.getLogger('bcm-node-labeler')

    def _get_node_name(self) -> str:
        """Get Kubernetes node name from environment or hostname"""
        node_name = os.getenv('NODE_NAME')
        if not node_name:
            node_name = socket.gethostname()
            self.logger.warning(f"NODE_NAME not set, using hostname: {node_name}")
        return node_name

    def _setup_metrics(self) -> Dict:
        """Set up Prometheus metrics"""
        metrics = {
            'node_info': Info('bcm_node', 'BCM node information'),
            'hardware_health': Gauge('bcm_hardware_health', 'Hardware health status',
                                    ['component']),
            'gpu_count': Gauge('bcm_gpu_count', 'Number of GPUs detected'),
            'cpu_count': Gauge('bcm_cpu_count', 'Number of CPUs'),
            'memory_gb': Gauge('bcm_memory_gb', 'Total memory in GB'),
            'last_sync': Gauge('bcm_last_sync_timestamp', 'Last BCM sync timestamp'),
        }
        return metrics

    def read_bcm_data(self) -> Optional[Dict]:
        """
        Read hardware data from BCM.

        In future, this will read from cm-lite-daemon's shared state.
        For now, read from system files or BCM config if available.
        """
        # TODO: Integrate with cm-lite-daemon to get real-time BCM data
        # For now, return basic system information

        try:
            data = {
                'node_name': self.node_name,
                'timestamp': time.time(),
            }

            # Try to read cm-lite-daemon config if available
            config_file = '/etc/bcm-agent/config.json'
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    data.update(config)

            return data

        except Exception as e:
            self.logger.error(f"Failed to read BCM data: {e}")
            return None

    def generate_labels(self, bcm_data: Dict) -> Dict[str, str]:
        """
        Generate Kubernetes labels from BCM data.

        Args:
            bcm_data: Hardware information from BCM

        Returns:
            Dictionary of label key-value pairs
        """
        labels = {}

        # Basic node info
        if 'node_name' in bcm_data:
            labels['node-name'] = bcm_data['node_name']

        # BCM cluster info
        if 'host' in bcm_data:
            labels['bcm-cluster'] = bcm_data['host']

        # Hardware info (will be populated when cm-lite-daemon integration is complete)
        # labels['gpu-count'] = str(bcm_data.get('gpu_count', 0))
        # labels['cpu-model'] = bcm_data.get('cpu_model', 'unknown')
        # labels['memory-gb'] = str(bcm_data.get('memory_gb', 0))

        # Health status
        # labels['health-status'] = bcm_data.get('health_status', 'unknown')

        self.logger.debug(f"Generated labels: {labels}")
        return labels

    def update_metrics(self, bcm_data: Dict):
        """Update Prometheus metrics with BCM data"""
        try:
            # Update node info
            self.metrics['node_info'].info({
                'node_name': bcm_data.get('node_name', 'unknown'),
                'bcm_cluster': bcm_data.get('host', 'unknown'),
            })

            # Update timestamp
            self.metrics['last_sync'].set(bcm_data.get('timestamp', time.time()))

            # Hardware metrics (placeholders for now)
            self.metrics['gpu_count'].set(bcm_data.get('gpu_count', 0))
            self.metrics['cpu_count'].set(bcm_data.get('cpu_count', 0))
            self.metrics['memory_gb'].set(bcm_data.get('memory_gb', 0))

            self.logger.debug("Updated Prometheus metrics")

        except Exception as e:
            self.logger.error(f"Failed to update metrics: {e}")

    def sync_node_labels(self):
        """Read BCM data and update Kubernetes node labels"""
        try:
            # Read hardware data from BCM
            bcm_data = self.read_bcm_data()
            if not bcm_data:
                self.logger.warning("No BCM data available, skipping sync")
                return

            # Update Prometheus metrics
            self.update_metrics(bcm_data)

            # Update Kubernetes labels
            if self.k8s_client and not self.args.disable_labeling:
                labels = self.generate_labels(bcm_data)
                if labels:
                    success = self.k8s_client.apply_labels(labels)
                    if success:
                        self.logger.info(f"Applied {len(labels)} labels to node {self.node_name}")
                    else:
                        self.logger.error("Failed to apply labels")
                else:
                    self.logger.warning("No labels generated from BCM data")

        except Exception as e:
            self.logger.error(f"Error during node label sync: {e}", exc_info=True)

    def run(self):
        """Main daemon loop"""
        self.logger.info(f"Starting BCM Node Labeler for {self.node_name}")
        self.logger.info(f"Label prefix: {self.args.label_prefix}")
        self.logger.info(f"Sync interval: {self.args.interval}s")

        # Start Prometheus metrics server
        if self.args.metrics_port:
            try:
                start_http_server(self.args.metrics_port)
                self.logger.info(f"Prometheus metrics exposed on port {self.args.metrics_port}")
            except Exception as e:
                self.logger.error(f"Failed to start metrics server: {e}")

        # Initial sync
        self.sync_node_labels()

        # Main loop
        while self.running:
            try:
                time.sleep(self.args.interval)
                self.sync_node_labels()

            except KeyboardInterrupt:
                self.logger.info("Received shutdown signal")
                self.running = False
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(5)  # Brief pause before retry

        self.logger.info("BCM Node Labeler stopped")


def main():
    parser = argparse.ArgumentParser(
        description='BCM Node Labeler - Kubernetes integration for BCM Agent'
    )

    parser.add_argument(
        '--interval',
        type=int,
        default=int(os.getenv('SYNC_INTERVAL', '300')),
        help='Sync interval in seconds (default: 300)'
    )

    parser.add_argument(
        '--label-prefix',
        type=str,
        default=os.getenv('LABEL_PREFIX', 'bcm.nvidia.com'),
        help='Kubernetes label prefix (default: bcm.nvidia.com)'
    )

    parser.add_argument(
        '--metrics-port',
        type=int,
        default=int(os.getenv('METRICS_PORT', '9100')),
        help='Prometheus metrics port (default: 9100)'
    )

    parser.add_argument(
        '--disable-labeling',
        action='store_true',
        help='Disable Kubernetes labeling (metrics only)'
    )

    parser.add_argument(
        '--metrics-only',
        action='store_true',
        help='Run in metrics-only mode (no K8s API required)'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    try:
        labeler = BCMNodeLabeler(args)
        labeler.run()
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
