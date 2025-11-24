#!/bin/bash
# SPDX-FileCopyrightText: Copyright 2025 Fabien Dupont <fdupont@redhat.com>
# SPDX-License-Identifier: Apache-2.0
#
# Build script for BCM Agent container image
# This script must be run on the BCM head node or a system with access to cm-lite-daemon distribution
#
# Usage:
#   ./scripts/build-image.sh [options]
#
# Options:
#   --registry <registry>    Target registry (default: local only)
#   --tag <tag>             Image tag (default: latest)
#   --push                  Push to registry after build
#   --openshift             Push to OpenShift internal registry
#   --help                  Show this help message

set -e

# Configuration
CM_LITE_DAEMON_ZIP="${CM_LITE_DAEMON_ZIP:-/cm/shared/apps/cm-lite-daemon-dist/cm-lite-daemon.zip}"
IMAGE_NAME="bcm-agent"
IMAGE_TAG="latest"
REGISTRY=""
PUSH=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --registry)
            REGISTRY="$2"
            shift 2
            ;;
        --tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --push)
            PUSH=true
            shift
            ;;
        --openshift)
            REGISTRY="image-registry.openshift-image-registry.svc:5000/default"
            shift
            ;;
        --help)
            grep "^#" "$0" | grep -v "^#!/" | sed 's/^# //'
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Determine full image name
if [ -n "$REGISTRY" ]; then
    FULL_IMAGE_NAME="$REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
else
    FULL_IMAGE_NAME="$IMAGE_NAME:$IMAGE_TAG"
fi

echo "========================================="
echo "BCM Agent Container Image Builder"
echo "========================================="
echo "Image: $FULL_IMAGE_NAME"
echo "Build context: $(pwd)"
echo ""

# Check if cm-lite-daemon.zip exists in BCM installation
if [ ! -f "$CM_LITE_DAEMON_ZIP" ]; then
    echo "ERROR: NVIDIA cm-lite-daemon not found at: $CM_LITE_DAEMON_ZIP"
    echo ""
    echo "This file is required to build the container image."
    echo "Please ensure you are running this script on a BCM head node"
    echo "or set CM_LITE_DAEMON_ZIP to the correct path."
    exit 1
fi

echo "Found NVIDIA cm-lite-daemon: $CM_LITE_DAEMON_ZIP"
echo ""

# Check if we're in the right directory
if [ ! -f "Containerfile" ]; then
    echo "ERROR: Containerfile not found in current directory"
    echo "Please run this script from the repository root"
    exit 1
fi

# Copy cm-lite-daemon.zip to build context
echo "Copying cm-lite-daemon.zip to build context..."
cp "$CM_LITE_DAEMON_ZIP" ./cm-lite-daemon.zip

# Ensure cleanup on exit
cleanup() {
    if [ -f ./cm-lite-daemon.zip ]; then
        echo "Cleaning up cm-lite-daemon.zip..."
        rm -f ./cm-lite-daemon.zip
    fi
}
trap cleanup EXIT

# Build the container image
echo ""
echo "Building container image..."
echo "Command: podman build -t $FULL_IMAGE_NAME ."
echo ""

if podman build -t "$FULL_IMAGE_NAME" .; then
    echo ""
    echo "========================================="
    echo "SUCCESS!"
    echo "========================================="
    echo "Image built: $FULL_IMAGE_NAME"
    echo ""

    # Show image details
    podman images "$FULL_IMAGE_NAME"
    echo ""

    # Push if requested
    if [ "$PUSH" = true ]; then
        echo "Pushing image to registry..."
        if podman push "$FULL_IMAGE_NAME"; then
            echo "Image pushed successfully!"
            echo ""
            echo "You can now deploy using:"
            echo "  helm install bcm-agent ./helm/bcm-agent \\"
            echo "    --set image.repository=$(echo "$FULL_IMAGE_NAME" | cut -d: -f1) \\"
            echo "    --set image.tag=$IMAGE_TAG"
        else
            echo "ERROR: Failed to push image"
            exit 1
        fi
    else
        echo "Next steps:"
        echo ""
        echo "1. Test the image locally:"
        echo "   podman run --rm -it $FULL_IMAGE_NAME /bin/bash"
        echo ""
        echo "2. Push to registry:"
        echo "   podman push $FULL_IMAGE_NAME"
        echo ""
        echo "3. Deploy with Helm:"
        echo "   helm install bcm-agent ./helm/bcm-agent \\"
        echo "     --set image.repository=$(echo "$FULL_IMAGE_NAME" | cut -d: -f1) \\"
        echo "     --set image.tag=$IMAGE_TAG"
    fi
    echo ""
else
    echo ""
    echo "ERROR: Build failed"
    exit 1
fi
