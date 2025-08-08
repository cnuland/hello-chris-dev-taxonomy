#!/bin/bash

# DSPA Deployment Script
# This script deploys the Data Science Pipelines Application with InstructLab pipeline support

set -e

NAMESPACE="petloan-instructlab"

echo "🚀 Starting DSPA deployment..."

# Check if OpenShift CLI is available
if ! command -v oc &> /dev/null; then
    echo "❌ OpenShift CLI (oc) is not installed or not in PATH"
    exit 1
fi

# Check if logged into OpenShift
if ! oc whoami &> /dev/null; then
    echo "❌ Not logged into OpenShift. Please run 'oc login' first"
    exit 1
fi

# Create namespace if it doesn't exist
echo "📁 Creating namespace: $NAMESPACE"
oc create namespace $NAMESPACE --dry-run=client -o yaml | oc apply -f -

# Apply resources in order
echo "🔧 Deploying service account and RBAC..."
oc apply -f 02-service-account.yaml

echo "🔐 Deploying secrets (please update with your actual credentials)..."
oc apply -f 03-secrets.yaml

echo "🏗️  Deploying DSPA..."
oc apply -f 01-dspa.yaml

# Wait for DSPA to be ready
echo "⏳ Waiting for DSPA to be ready..."
timeout=600  # 10 minutes
elapsed=0
interval=30

while [ $elapsed -lt $timeout ]; do
    if oc get dspa dspa -n $NAMESPACE &> /dev/null; then
        # Check if at least the API server pod is running
        if oc get pods -n $NAMESPACE -l app=ds-pipeline-dspa --no-headers 2>/dev/null | grep -q "Running"; then
            echo "✅ DSPA API server is running"
            break
        fi
    fi
    
    echo "⏳ Still waiting for DSPA components to start... (${elapsed}s elapsed)"
    sleep $interval
    elapsed=$((elapsed + interval))
done

if [ $elapsed -ge $timeout ]; then
    echo "⚠️  Timeout waiting for DSPA to be ready, but continuing..."
    echo "   You can check the status with: oc describe dspa dspa -n $NAMESPACE"
else
    echo "✅ DSPA deployment completed successfully!"
fi

echo ""
echo "📋 Deployment Summary:"
echo "   Namespace: $NAMESPACE"
echo "   DSPA: dspa"
echo "   Service Account: pipeline-runner-dspa"
echo ""
echo "🔗 Useful commands:"
echo "   Check DSPA status: oc describe dspa dspa -n $NAMESPACE"
echo "   View pods: oc get pods -n $NAMESPACE"
echo "   View services: oc get svc -n $NAMESPACE"
echo "   View routes: oc get routes -n $NAMESPACE"
echo ""
echo "📝 Next steps:"
echo "   1. Update the secrets in 03-secrets.yaml with your actual credentials"
echo "   2. Redeploy secrets: oc apply -f 03-secrets.yaml"
echo "   3. Follow the README.md for pipeline submission instructions"
echo ""
echo "🎉 DSPA is ready for InstructLab pipeline operations!"
