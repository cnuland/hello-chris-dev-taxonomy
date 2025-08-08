#!/bin/bash

# InstructLab Pipeline Environment Check
# This script validates the prerequisites before deploying the InstructLab pipeline

set -e

echo "🔍 InstructLab Pipeline - Environment Prerequisites Check"
echo "======================================================="
echo ""

FAILED=0

# Check if running on correct OS
echo -n "🖥️  Checking operating system... "
OS=$(uname -s)
if [[ "$OS" == "Darwin" ]] || [[ "$OS" == "Linux" ]]; then
    echo "✅ $OS (supported)"
else
    echo "⚠️  $OS (untested, may work)"
fi

# Check for OpenShift CLI
echo -n "🛠️  Checking OpenShift CLI (oc)... "
if command -v oc &> /dev/null; then
    OC_VERSION=$(oc version --client -o json 2>/dev/null | grep -o '"gitVersion":"[^"]*"' | cut -d'"' -f4 2>/dev/null || echo "unknown")
    echo "✅ Found (version: $OC_VERSION)"
else
    echo "❌ Not found - Install from https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html"
    FAILED=1
fi

# Check OpenShift login status
echo -n "🔐 Checking OpenShift login status... "
if oc whoami &> /dev/null; then
    USER=$(oc whoami)
    CLUSTER=$(oc whoami --show-server 2>/dev/null || echo "unknown")
    echo "✅ Logged in as: $USER"
    echo "    Cluster: $CLUSTER"
else
    echo "❌ Not logged in - Run 'oc login' first"
    FAILED=1
fi

# Check for Python
echo -n "🐍 Checking Python... "
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>/dev/null | cut -d' ' -f2)
    echo "✅ Found Python $PYTHON_VERSION"
    
    # Check Python version is 3.8+
    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
        echo "    ✅ Version 3.8+ requirement met"
    else
        echo "    ⚠️  Version 3.8+ recommended, found $PYTHON_VERSION"
    fi
else
    echo "❌ Not found - Install Python 3.8+ from https://python.org"
    FAILED=1
fi

# Check for required Python packages
echo -n "📦 Checking Python packages... "
MISSING_PACKAGES=()
for pkg in requests yaml urllib3; do
    if ! python3 -c "import $pkg" &> /dev/null; then
        MISSING_PACKAGES+=($pkg)
    fi
done

if [ ${#MISSING_PACKAGES[@]} -eq 0 ]; then
    echo "✅ All required packages found"
else
    echo "⚠️  Missing packages: ${MISSING_PACKAGES[*]}"
    echo "    Install with: pip install -r dspa-deployment/requirements.txt"
fi

# Check for Git
echo -n "📚 Checking Git... "
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version | cut -d' ' -f3)
    echo "✅ Found Git $GIT_VERSION"
else
    echo "❌ Not found - Install from https://git-scm.com"
    FAILED=1
fi

# Check for curl
echo -n "🌐 Checking curl... "
if command -v curl &> /dev/null; then
    echo "✅ Found"
else
    echo "❌ Not found - Install curl for API testing"
    FAILED=1
fi

# Check OpenShift cluster access and version
if oc whoami &> /dev/null; then
    echo -n "🏗️  Checking OpenShift cluster version... "
    if OCP_VERSION=$(oc version -o json 2>/dev/null | grep -o '"gitVersion":"[^"]*"' | tail -1 | cut -d'"' -f4 2>/dev/null); then
        echo "✅ Found OpenShift $OCP_VERSION"
        
        # Extract major.minor version for comparison
        if [[ "$OCP_VERSION" =~ ^[0-9]+\.[0-9]+ ]]; then
            VERSION_NUM=$(echo "$OCP_VERSION" | sed 's/^v//' | cut -d'.' -f1,2)
            if awk "BEGIN {exit !($VERSION_NUM >= 4.14)}" 2>/dev/null; then
                echo "    ✅ Version 4.14+ requirement met"
            else
                echo "    ⚠️  Version 4.14+ recommended, found $OCP_VERSION"
            fi
        fi
    else
        echo "⚠️  Could not determine version"
    fi
fi

# Check for OpenShift AI operator
if oc whoami &> /dev/null; then
    echo -n "🤖 Checking OpenShift AI installation... "
    if oc get csv -A --no-headers 2>/dev/null | grep -q "rhods-operator"; then
        echo "✅ OpenShift AI operator found"
    elif oc get csv -A --no-headers 2>/dev/null | grep -q "opendatahub"; then
        echo "✅ Open Data Hub operator found (compatible)"
    else
        echo "⚠️  OpenShift AI/ODH operator not found"
        echo "    Install via: Operators → OperatorHub → Red Hat OpenShift AI"
    fi
fi

echo ""
echo "📊 Prerequisites Summary:"
echo "========================"

if [ $FAILED -eq 0 ]; then
    echo "🎉 All essential prerequisites are met!"
    echo ""
    echo "🚀 Next steps:"
    echo "   1. Navigate to deployment directory: cd dspa-deployment"
    echo "   2. Configure secrets: vim 03-secrets.yaml"
    echo "   3. Deploy DSPA: ./deploy.sh"
    echo "   4. Validate deployment: ./validate.sh"
    echo ""
    echo "📖 For detailed instructions, see: dspa-deployment/README.md"
    
    exit 0
else
    echo "❌ $FAILED essential prerequisite(s) missing."
    echo ""
    echo "🔧 Required actions:"
    echo "   - Install missing tools listed above"
    echo "   - Login to OpenShift cluster with 'oc login'"
    echo "   - Ensure you have cluster-admin or appropriate permissions"
    echo ""
    echo "📖 For help, see the main README.md or dspa-deployment/README.md"
    
    exit 1
fi
