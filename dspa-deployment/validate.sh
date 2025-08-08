#!/bin/bash

# DSPA Deployment Validation Script
# This script validates that the DSPA deployment is healthy and ready for pipeline operations

set -e

NAMESPACE="petloan-instructlab"
FAILED=0

echo "🔍 Validating DSPA deployment in namespace: $NAMESPACE"
echo "============================================="

# Check if namespace exists
echo -n "📁 Checking namespace exists... "
if oc get namespace $NAMESPACE &>/dev/null; then
    echo "✅ PASS"
else
    echo "❌ FAIL - Namespace '$NAMESPACE' not found"
    FAILED=1
fi

# Check DSPA resource exists
echo -n "🏗️  Checking DSPA resource exists... "
if oc get dspa dspa -n $NAMESPACE &>/dev/null; then
    echo "✅ PASS"
else
    echo "❌ FAIL - DSPA 'dspa' not found"
    FAILED=1
fi

# Check service account
echo -n "👤 Checking service account... "
if oc get serviceaccount pipeline-runner-dspa -n $NAMESPACE &>/dev/null; then
    echo "✅ PASS"
else
    echo "❌ FAIL - ServiceAccount 'pipeline-runner-dspa' not found"
    FAILED=1
fi

# Check cluster role binding
echo -n "🔐 Checking RBAC permissions... "
if oc get clusterrolebinding pipeline-runner-dspa &>/dev/null; then
    echo "✅ PASS"
else
    echo "❌ FAIL - ClusterRoleBinding 'pipeline-runner-dspa' not found"
    FAILED=1
fi

# Check secrets
echo -n "🔑 Checking required secrets... "
SECRETS_OK=true
for secret in teacher-secret judge-secret taxonomy-repo-secret oci-output-push-secret; do
    if ! oc get secret $secret -n $NAMESPACE &>/dev/null; then
        echo -e "\n   ❌ Missing secret: $secret"
        SECRETS_OK=false
        FAILED=1
    fi
done
if $SECRETS_OK; then
    echo "✅ PASS"
fi

# Check core pods are running
echo -n "🏃 Checking core pods are running... "
PODS_OK=true
expected_pods=("ds-pipeline-dspa" "mariadb-dspa" "minio-dspa" "ds-pipeline-persistenceagent-dspa" "ds-pipeline-scheduledworkflow-dspa" "ds-pipeline-workflow-controller-dspa")

for pod_prefix in "${expected_pods[@]}"; do
    if ! oc get pods -n $NAMESPACE --no-headers 2>/dev/null | grep -q "^${pod_prefix}.*Running"; then
        if $PODS_OK; then
            echo ""  # Start new line for pod failures
        fi
        echo "   ❌ Pod with prefix '$pod_prefix' not running or not found"
        PODS_OK=false
        FAILED=1
    fi
done
if $PODS_OK; then
    echo "✅ PASS"
fi

# Check services
echo -n "🌐 Checking required services... "
SERVICES_OK=true
expected_services=("ds-pipeline-dspa" "mariadb-dspa" "minio-dspa")

for service in "${expected_services[@]}"; do
    if ! oc get service $service -n $NAMESPACE &>/dev/null; then
        if $SERVICES_OK; then
            echo ""
        fi
        echo "   ❌ Service '$service' not found"
        SERVICES_OK=false
        FAILED=1
    fi
done
if $SERVICES_OK; then
    echo "✅ PASS"
fi

# Check routes
echo -n "🛣️  Checking external routes... "
if oc get route ds-pipeline-dspa -n $NAMESPACE &>/dev/null; then
    echo "✅ PASS"
else
    echo "⚠️  WARN - Route 'ds-pipeline-dspa' not found (may be expected)"
fi

# Check DSPA status conditions
echo -n "📋 Checking DSPA status conditions... "
if oc get dspa dspa -n $NAMESPACE -o jsonpath='{.status.conditions}' 2>/dev/null | grep -q '"status":"True"'; then
    echo "✅ PASS"
else
    echo "⚠️  WARN - DSPA may not be fully ready yet"
    echo "   Check: oc describe dspa dspa -n $NAMESPACE"
fi

# Check MinIO connectivity (common issue)
echo -n "🗄️  Testing MinIO connectivity... "
if oc get pods -n $NAMESPACE --no-headers 2>/dev/null | grep -q "^minio-dspa.*Running"; then
    echo "✅ PASS"
else
    echo "❌ FAIL - MinIO pod not running"
    FAILED=1
fi

# Check for managed pipeline (InstructLab)
echo -n "🔬 Checking for managed pipeline... "
if timeout 10 oc port-forward -n $NAMESPACE svc/ds-pipeline-dspa 8889:8888 >/dev/null 2>&1 & 
 then
    PF_PID=$!
    sleep 2
    if curl -k -s -f https://localhost:8889/apis/v2beta1/pipelines --max-time 5 >/dev/null 2>&1; then
        echo "✅ PASS - API accessible"
    else
        echo "⚠️  WARN - API not accessible yet (may need more time)"
    fi
    kill $PF_PID 2>/dev/null || true
else
    echo "⚠️  WARN - Could not test API connectivity"
fi

echo ""
echo "📊 Validation Summary:"
echo "====================="

if [ $FAILED -eq 0 ]; then
    echo "🎉 All checks passed! DSPA deployment is healthy."
    echo ""
    echo "🚀 Next steps:"
    echo "   1. Update secrets with your actual credentials:"
    echo "      oc apply -f 03-secrets.yaml"
    echo ""
    echo "   2. Test pipeline submission:"
    echo "      # Start port-forwarding (in another terminal)"
    echo "      oc port-forward -n $NAMESPACE svc/ds-pipeline-dspa 8888:8888"
    echo ""
    echo "      # Submit a test pipeline"
    echo "      python3 submit_pipeline.py --repo-url YOUR_REPO_URL"
    echo ""
    echo "   3. Monitor pipeline runs:"
    echo "      oc get pods -n $NAMESPACE | grep instructlab"
    
    exit 0
else
    echo "❌ $FAILED check(s) failed. Please review the issues above."
    echo ""
    echo "🔧 Common troubleshooting steps:"
    echo "   - Re-run: ./deploy.sh"
    echo "   - Check resources: oc describe dspa dspa -n $NAMESPACE" 
    echo "   - Check events: oc get events -n $NAMESPACE --sort-by='.lastTimestamp'"
    echo "   - Check logs: oc logs <pod-name> -n $NAMESPACE"
    
    exit 1
fi
