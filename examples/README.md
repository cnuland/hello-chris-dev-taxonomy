# Examples

This directory contains example configurations and optional deployments for the InstructLab pipeline.

## Model Deployments

The `model-deployments/` directory contains example KServe model serving configurations:

- `teacher-model-deployment.yaml` - Mixtral-8x7B teacher model serving
- `judge-model-deployment.yaml` - Prometheus judge model serving  
- `mixtral-deployment.yaml` - Alternative Mixtral deployment configuration
- `prometheus-deployment.yaml` - Alternative Prometheus deployment configuration

These are optional - you can use external model endpoints instead of deploying these locally.

## Usage

To deploy example model services:

```bash
# Deploy teacher model
oc apply -f model-deployments/teacher-model-deployment.yaml

# Deploy judge model  
oc apply -f model-deployments/judge-model-deployment.yaml
```

For the main DSPA deployment, use the files in the `dspa-deployment/` directory instead.
