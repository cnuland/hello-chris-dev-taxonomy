# DSPA InstructLab Pipeline Deployment

This repository contains everything needed to deploy a Data Science Pipelines Application (DSPA) on OpenShift with support for the InstructLab synthetic data generation and model training pipeline.

## Recent updates (August 2025)

- Added a direct Argo Workflow path to run the InstructLab pipeline while the DSPA API is returning 500 (MariaDB query error):
  - rbac-argo-workflow.yaml: service account and RBAC for workflows
  - wf-check.yaml: quick PVC/scheduling validation workflow
  - instructlab-argo-workflow.yaml: production workflow using CPU for early stages and GPU only for training
- Storage changes:
  - Use AWS EBS gp3 ReadWriteOnce (RWO) PVCs only; removed RWX assumptions
  - Rely on WaitForFirstConsumer binding to avoid premature PVC scheduling issues
- Scheduling changes:
  - SDG, data-processing, and training-setup tasks are CPU-only (no GPU request)
  - Training tasks request 1x GPU and include toleration for `nvidia.com/gpu=true:NoSchedule` and nodeSelector `nvidia.com/gpu.present: "true"`
- Monitoring and troubleshooting guidance updated to include Argo CLI flow
- Cleaned up NFS-related manifests; the current recommended path is gp3 RWO PVCs

To use the Argo direct path quickly:

```
# 1) Create SA/RBAC
kubectl apply -f rbac-argo-workflow.yaml

# 2) Validate storage/scheduling
kubectl apply -f wf-check.yaml
kubectl -n petloan-instructlab get workflow ilab-storage-sched-check -o jsonpath='{.status.phase}\n'

# 3) Launch pipeline
kubectl create -f instructlab-argo-workflow.yaml
kubectl -n petloan-instructlab get workflows

# 4) Monitor
kubectl -n petloan-instructlab get pods -l workflows.argoproj.io/workflow=<workflow-name>
kubectl -n petloan-instructlab get workflow <workflow-name> -o jsonpath='{.status.phase} {.status.message}\n'
```

## Overview

The InstructLab pipeline enables automated fine-tuning of Large Language Models (LLMs) using synthetic data generation, evaluation, and training workflows. This deployment includes:

- **DSPA**: Data Science Pipelines Application with Kubeflow Pipelines v2
- **Managed Pipeline**: Pre-registered InstructLab pipeline for SDG and training
- **Storage**: MinIO object storage and MariaDB database  
- **Authentication**: Service account with proper RBAC permissions
- **Secrets**: Template configurations for model endpoints and credentials

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    OpenShift Namespace                          │
│                   (petloan-instructlab)                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────────┐ │
│  │   DSPA API      │  │     MinIO       │  │      MariaDB       │ │
│  │   Server        │  │   (Storage)     │  │    (Metadata)      │ │
│  │                 │  │                 │  │                    │ │
│  └─────────────────┘  └─────────────────┘  └────────────────────┘ │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────────┐ │
│  │  Workflow       │  │  Persistence    │  │   InstructLab      │ │
│  │  Controller     │  │    Agent        │  │    Pipeline        │ │
│  │                 │  │                 │  │   (Managed)        │ │
│  └─────────────────┘  └─────────────────┘  └────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

### OpenShift Cluster Requirements
- OpenShift 4.12+
- Red Hat OpenShift AI (RHOAI) operator installed
- Data Science Pipelines operator available
- Sufficient compute resources for pipeline workloads

### Client Requirements
- OpenShift CLI (`oc`) installed and configured
- Python 3.8+ with `requests`, `yaml`, `urllib3` packages
- Access to container registries (for model images)
- Git repository access (for taxonomy data)

### Resource Requirements (Recommended)
- **CPU**: 8+ cores available for pipeline pods
- **Memory**: 32GB+ available for training workloads  
- **Storage**: 100GB+ for models, datasets, and pipeline artifacts
- **Network**: Ability to pull container images from registries

## Quick Start

### 1. Clone and Prepare

```bash
# Navigate to deployment directory
cd dspa-deployment

# Review and customize configuration
vim 03-secrets.yaml  # Update with your credentials
```

### 2. Update Secrets Configuration

Edit `03-secrets.yaml` with your actual values:

```yaml
# Teacher Model Secret - Update endpoint details
stringData:
  api_key: "your-teacher-model-api-key"
  model: "your-teacher-model-name"
  url: "http://your-teacher-model-service:8000/v1"

# Judge Model Secret - Update endpoint details  
stringData:
  api_key: "your-judge-model-api-key"
  url: "http://your-judge-model-service:8000/v1"

# Taxonomy Repository Secret - Update Git credentials
stringData:
  username: "your-github-username"
  password: "ghp_your-github-token"

# OCI Registry Secret - Update registry credentials
stringData:
  .dockerconfigjson: |
    {
      "auths": {
        "quay.io": {
          "username": "your-quay-username", 
          "password": "your-quay-password-or-token"
        }
      }
    }
```

### 3. Deploy DSPA

```bash
# Make deployment script executable
chmod +x deploy.sh

# Deploy all resources
./deploy.sh
```

### 4. Verify Deployment

```bash
# Check DSPA status
oc describe dspa dspa -n petloan-instructlab

# Check all pods are running
oc get pods -n petloan-instructlab

# Verify services
oc get svc -n petloan-instructlab

# Check routes
oc get routes -n petloan-instructlab
```

## Pipeline Submission

### Method 1: Port Forwarding (Recommended)

Port forwarding bypasses OAuth complications and provides direct API access:

```bash
# Start port forwarding (in separate terminal)
oc port-forward -n petloan-instructlab svc/ds-pipeline-dspa 8888:8888

# Submit pipeline run with tested defaults
python3 submit_pipeline.py

# Or with custom parameters (use tested base models)
python3 submit_pipeline.py \
    --repo-url "https://github.com/your-org/taxonomy.git" \
    --base-model "microsoft/DialoGPT-medium" \
    --output-model-name "my-fine-tuned-model"
```

### Method 2: OAuth Route

Using the external OpenShift route (may require additional OAuth setup):

```bash
# Submit via route
python3 submit_pipeline.py --route
```

## Pipeline Parameters

The InstructLab pipeline supports numerous configuration parameters:

### Required Parameters
| Parameter | Description | Example |
|-----------|-------------|---------|
| `sdg_repo_url` | Taxonomy repository URL | `https://github.com/instructlab/taxonomy.git` |
| `sdg_base_model` | Base model for fine-tuning | `registry.redhat.io/rhelai1/granite-7b-starter` |
| `output_model_name` | Name for the fine-tuned model | `fine-tuned-granite-7b` |
| `output_model_registry_api_url` | Model registry API endpoint | `https://model-registry.example.com` |
| `output_oci_registry_secret` | Secret for OCI registry push | `oci-output-push-secret` |

### Optional Parameters (with defaults)
| Parameter | Default | Description |
|-----------|---------|-------------|
| `sdg_scale_factor` | 30 | Synthetic data generation scale |
| `train_num_epochs_phase_1` | 7 | Training epochs for phase 1 |
| `train_num_epochs_phase_2` | 10 | Training epochs for phase 2 |
| `train_batch_size_phase_1` | 8 | Batch size for phase 1 training |
| `train_learning_rate_phase_1` | 2e-6 | Learning rate for phase 1 |

## Monitoring Pipeline Runs

### Via OpenShift Console
1. Navigate to the DSPA route: `oc get routes -n petloan-instructlab`
2. Access the Kubeflow Pipelines UI
3. Monitor runs, view logs, and check artifacts

### Via CLI Commands
```bash
# List pipeline runs
oc get pods -n petloan-instructlab | grep instructlab

# View pipeline logs
oc logs -n petloan-instructlab <pod-name> -c main

# Monitor resource usage
oc top pods -n petloan-instructlab

# Check events
oc get events -n petloan-instructlab --sort-by='.lastTimestamp'
```

### Via Python Script
```bash
# Check pipeline status
python3 -c "
import requests
response = requests.get('https://localhost:8888/apis/v2beta1/runs', 
                       headers={'Authorization': 'Bearer YOUR_TOKEN'}, 
                       verify=False)
print(response.json())
"
```

## Troubleshooting

### Common Issues

#### 1. DSPA Components Not Starting
```bash
# Check DSPA status
oc describe dspa dspa -n petloan-instructlab

# Check pod events
oc describe pod <pod-name> -n petloan-instructlab

# Common fixes:
# - Verify secrets are properly configured
# - Check resource quotas and limits
# - Ensure proper RBAC permissions
```

#### 2. Pipeline Submission Failures
```bash
# Check authentication
oc whoami -t

# Verify port-forwarding
curl -k https://localhost:8888/apis/v2beta1/pipelines \
  -H "Authorization: Bearer $(oc whoami -t)"

# Common fixes:
# - Restart port-forwarding
# - Check OpenShift login status
# - Verify DSPA API server is running
```

#### 3. Pipeline Run Failures
```bash
# Check pipeline pod logs
oc logs <pipeline-pod> -n petloan-instructlab

# Check resource requirements
oc describe pod <pipeline-pod> -n petloan-instructlab

# Common fixes:
# - Update resource requests/limits
# - Verify secret references
# - Check node selectors and tolerations
```

#### 4. MinIO Connectivity Issues
```bash
# Check MinIO pod
oc get pods -n petloan-instructlab | grep minio

# Verify MinIO service
oc get svc minio-dspa -n petloan-instructlab

# Test connectivity
oc run debug-pod --image=curlimages/curl --rm -it -- /bin/sh
curl http://minio-dspa.petloan-instructlab.svc.cluster.local:9000
```

## Security Considerations

### Secrets Management
- Regularly rotate API keys and tokens
- Use dedicated service accounts for pipeline operations
- Store sensitive data in OpenShift secrets, not ConfigMaps
- Enable secret encryption at rest

### Network Security
- Configure network policies to restrict pod-to-pod communication
- Use TLS for all API communications (enabled by default)
- Restrict external route access if not needed
- Monitor network traffic for anomalies

### RBAC and Permissions
- Follow principle of least privilege for service accounts
- Regularly audit cluster role bindings
- Use namespace isolation for different environments
- Implement resource quotas and limits

## Advanced Configuration

### Custom Node Selection
```yaml
# In pipeline parameters
train_node_selectors:
  node-type: "gpu-enabled"
  zone: "us-west-1a"

train_tolerations:
  - key: "nvidia.com/gpu"
    operator: "Exists"
    effect: "NoSchedule"
```

### Resource Limits
```yaml
# Custom resource requirements
train_cpu_limit: "8"
train_memory_limit: "32Gi"  
train_gpu_limit: "1"
```

### Storage Configuration
```yaml
# Custom PVC sizes in DSPA spec
database:
  mariaDB:
    pvcSize: 20Gi

objectStorage:
  minio:
    pvcSize: 50Gi
```

## File Structure

```
dspa-deployment/
├── README.md                 # This file
├── deploy.sh                 # Automated deployment script
├── submit_pipeline.py        # Pipeline submission script
├── 01-dspa.yaml             # DSPA configuration
├── 02-service-account.yaml  # Service account and RBAC
└── 03-secrets.yaml          # Secret templates
```

## Support and Contributing

### Getting Help
- Check OpenShift documentation for DSPA troubleshooting
- Review Kubeflow Pipelines documentation
- Consult Red Hat OpenShift AI documentation
- OpenShift community forums and support

### Contributing
- Submit issues for bugs or feature requests
- Contribute improvements via pull requests
- Update documentation for configuration changes
- Share deployment experiences and best practices

## License

This deployment configuration is provided as-is for educational and development purposes. Please review your organization's policies for production deployments.
