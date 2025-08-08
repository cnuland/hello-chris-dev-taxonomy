#!/bin/bash

# DSPA Deployment Packaging Script
# Creates a distributable tarball of the DSPA deployment resources

set -e

PACKAGE_NAME="dspa-instructlab-deployment-$(date +%Y%m%d-%H%M%S)"
TEMP_DIR="/tmp/$PACKAGE_NAME"

echo "📦 Creating DSPA InstructLab deployment package..."

# Create temporary directory
mkdir -p "$TEMP_DIR"

# Copy all deployment files
cp *.yaml *.sh *.py *.txt *.md "$TEMP_DIR/"

# Make scripts executable
chmod +x "$TEMP_DIR"/*.sh
chmod +x "$TEMP_DIR"/*.py

# Create tarball
echo "🗜️  Creating tarball: ${PACKAGE_NAME}.tar.gz"
tar -czf "${PACKAGE_NAME}.tar.gz" -C "/tmp" "$PACKAGE_NAME"

# Clean up temp directory
rm -rf "$TEMP_DIR"

echo "✅ Package created successfully!"
echo ""
echo "📋 Package Contents:"
tar -tzf "${PACKAGE_NAME}.tar.gz" | sort

echo ""
echo "🚀 To deploy on another cluster:"
echo "   1. Extract: tar -xzf ${PACKAGE_NAME}.tar.gz"
echo "   2. Navigate: cd $PACKAGE_NAME"
echo "   3. Configure: vim 03-secrets.yaml"
echo "   4. Deploy: ./deploy.sh"
echo "   5. Validate: ./validate.sh"
echo ""
echo "📁 Package location: $(pwd)/${PACKAGE_NAME}.tar.gz"
