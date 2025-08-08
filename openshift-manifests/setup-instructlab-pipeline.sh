#!/bin/bash
set -e

# Configuration
DS_PROJECT="petloan-instructlab"
DSPA_NAME="dspa"
MODEL_REGISTRY_NAME="model-registry"  # Change if different

echo "Setting up InstructLab pipeline for project: $DS_PROJECT"

# Check if logged in to OpenShift
if ! oc whoami >/dev/null 2>&1; then
    echo "Error: Not logged in to OpenShift. Please login first:"
    echo "oc login https://api.rhoai-cluster.qhxt.p1.openshiftapps.com:6443"
    exit 1
fi

# Create/switch to the data science project
echo "Creating/switching to data science project: $DS_PROJECT"
oc new-project $DS_PROJECT 2>/dev/null || oc project $DS_PROJECT

# Apply all the secrets
echo "Creating secrets..."
oc apply -f s3-credentials-secret.yaml
oc apply -f taxonomy-repo-secret.yaml
oc apply -f oci-output-secret.yaml

# Create DSPA to enable InstructLab pipeline
echo "Creating Data Science Pipelines Application..."
oc apply -f dspa-config.yaml

# Wait for DSPA to be ready
echo "Waiting for DSPA to become ready..."
oc wait --for=condition=Ready dspa/$DSPA_NAME --timeout=300s

# Apply model registry permissions
echo "Setting up model registry permissions..."
oc apply -f model-registry-permissions.yaml

# Alternatively, patch existing DSPA to enable InstructLab (if DSPA already exists)
echo "Patching DSPA to enable InstructLab pipeline..."
oc patch dspa ${DSPA_NAME} -n ${DS_PROJECT} --type=merge --patch='{"spec": { "apiServer": { "managedPipelines": { "instructLab": {"state": "Managed"}}}}}'

echo "Setup complete! The InstructLab pipeline should now be available in the RHOAI Dashboard."
echo ""
echo "Next steps:"
echo "1. Access the RHOAI Dashboard"
echo "2. Navigate to Data Science Pipelines"
echo "3. Create a new pipeline run using the 'InstructLab' pipeline"
echo "4. Configure the pipeline parameters:"
echo "   - Base model S3 path: s3://cnuland-ilab-models-1754270376/granite-starter/"
echo "   - Taxonomy repo: $(cd ../taxonomy && git remote get-url origin)"
echo "   - SDG repo secret: taxonomy-repo-secret"
echo "   - OCI output push secret: oci-output-push-secret"
echo "   - S3 credentials secret: s3-credentials"
