# InstructLab Pipeline Parameters

When running the InstructLab pipeline in RHOAI, you'll need to configure these parameters:

## Required Parameters

### Model Configuration
- **Input Model Path**: `s3://cnuland-ilab-models-1754270376/granite-starter/`
  - This is your base granite-7b-starter model uploaded to S3
  - The pipeline will download this model for fine-tuning

### Taxonomy Configuration
- **SDG Repository URL**: `https://github.com/cnuland/your-taxonomy-repo.git` 
  - Replace with your actual taxonomy repository URL
  - Can also use S3 path: `s3://cnuland-ilab-models-1754270376/taxonomy/`
- **SDG Repository Secret**: `taxonomy-repo-secret`
  - Used if your taxonomy repo is private
  - Leave empty if using public repo

### Output Configuration
- **OCI Output Registry**: `quay.io/cnuland/instructlab-models`
  - Where to push the fine-tuned model
  - Format: `registry/namespace/repository:tag`
- **OCI Output Push Secret**: `oci-output-push-secret`
  - Credentials for pushing to the output registry

### Storage Configuration
- **Storage Credentials Secret**: `s3-credentials`
  - AWS credentials for accessing S3 bucket with base model

## Optional Parameters

### Training Configuration
- **Number of Training Epochs**: `3` (default)
- **Learning Rate**: `1e-5` (default)
- **Batch Size**: `4` (default, adjust based on GPU memory)

### Resource Configuration
- **GPU Type**: Select appropriate GPU accelerator profile
- **Memory Limit**: Adjust based on model size and available resources

### Model Registry
- **Model Registry Name**: `model-registry`
- **Model Registry API URL**: Auto-detected from cluster

## Example Values

Here's a complete example of parameter values:

```
Input Model Path: s3://cnuland-ilab-models-1754270376/granite-starter/
SDG Repository URL: https://github.com/cnuland/petloan-taxonomy.git
SDG Repository Secret: taxonomy-repo-secret
OCI Output Registry: quay.io/cnuland/petloan-instructlab:latest
OCI Output Push Secret: oci-output-push-secret
Storage Credentials Secret: s3-credentials
Number of Training Epochs: 3
Learning Rate: 1e-5
Batch Size: 4
```

## Notes

1. **Model Size**: The granite-7b-starter model is ~12.6GB, ensure sufficient storage
2. **GPU Requirements**: Training requires GPUs, ensure your cluster has GPU nodes available
3. **Training Time**: Fine-tuning can take several hours depending on data size and resources
4. **Output Size**: The fine-tuned model will be similar in size to the base model
