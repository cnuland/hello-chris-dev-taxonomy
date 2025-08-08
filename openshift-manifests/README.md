# InstructLab Pipeline Setup on OpenShift AI

This directory contains all the necessary configuration files to set up the InstructLab pipeline on your RHOAI cluster.

## Prerequisites

✅ **Already Completed:**
- Granite-7b-starter model uploaded to S3: `s3://cnuland-ilab-models-1754270376/granite-starter/`
- Taxonomy repository: `https://github.com/cnuland/hello-chris-dev-taxonomy.git`
- PetLoan document: `s3://cnuland-ilab-models-1754270376/documents/PetLoan_Solutions_Technology_Practices.md`
- AWS credentials configured

## Setup Steps

### 1. Login to OpenShift
```bash
oc login https://api.rhoai-cluster.qhxt.p1.openshiftapps.com:6443
```

### 2. Run the setup script
```bash
cd openshift-manifests
./setup-instructlab-pipeline.sh
```

This script will:
- Create the `llm-d` data science project (or switch to it)
- Create all necessary secrets
- Set up the Data Science Pipelines Application (DSPA)
- Enable the InstructLab pipeline
- Configure model registry permissions

### 3. Access the RHOAI Dashboard
1. Navigate to your RHOAI cluster dashboard
2. Go to **Data Science Projects** → **llm-d**
3. Click on **Pipelines** → **Pipelines**
4. You should see the **InstructLab** pipeline listed

### 4. Create a Pipeline Run
1. Click **Create run** on the InstructLab pipeline
2. Configure the parameters (see PIPELINE_PARAMETERS.md for details):

**Key Parameters:**
- **Input Model Path**: `s3://cnuland-ilab-models-1754270376/granite-starter/`
- **SDG Repository URL**: `https://github.com/cnuland/hello-chris-dev-taxonomy.git`
- **SDG Repository Secret**: `taxonomy-repo-secret`
- **OCI Output Registry**: `quay.io/cnuland/petloan-instructlab:latest`
- **OCI Output Push Secret**: `oci-output-push-secret`
- **Storage Credentials Secret**: `s3-credentials`

3. Click **Create run** to start the pipeline

## Files Overview

- `s3-credentials-secret.yaml` - AWS credentials for S3 access
- `taxonomy-repo-secret.yaml` - Git credentials for taxonomy repository
- `oci-output-secret.yaml` - Registry credentials for output model
- `dspa-config.yaml` - Data Science Pipelines Application configuration
- `model-registry-permissions.yaml` - Permissions for model registry access
- `setup-instructlab-pipeline.sh` - Automated setup script
- `PIPELINE_PARAMETERS.md` - Detailed parameter documentation

## Resources Created

The setup creates these OpenShift resources:
- **Namespace**: `llm-d` (data science project)
- **Secrets**: 
  - `s3-credentials` (AWS credentials)
  - `taxonomy-repo-secret` (Git credentials)  
  - `oci-output-push-secret` (Registry credentials)
- **DSPA**: `dspa` (enables InstructLab pipeline)
- **RoleBinding**: Model registry access permissions

## Pipeline Workflow

1. **Download Base Model**: Downloads granite-7b-starter from S3
2. **Fetch Taxonomy**: Clones your taxonomy repository
3. **Generate Synthetic Data**: Creates training data from taxonomy
4. **Train Model**: Fine-tunes the base model on generated data
5. **Push Output**: Uploads the fine-tuned model to OCI registry
6. **Register Model**: Registers the model in the model registry

## Monitoring

- Monitor pipeline progress in the RHOAI dashboard
- Check logs for each pipeline step
- View resource usage in the OpenShift console
- Expected runtime: 2-4 hours depending on data size and resources

## Troubleshooting

Common issues:
1. **Authentication errors**: Ensure all secrets are created correctly
2. **Resource limitations**: Check GPU availability and memory limits
3. **Permission issues**: Verify model registry permissions are set up
4. **Storage access**: Confirm S3 credentials and bucket permissions

For detailed troubleshooting, see the [ilab-on-ocp troubleshooting guide](../ilab-on-ocp/docs/troubleshooting.md).

## Next Steps

After successful pipeline completion:
1. Verify the fine-tuned model in your OCI registry
2. Deploy the model for inference using KServe
3. Test the model with PetLoan-specific queries
4. Compare performance against the base model
