# InstructLab Pipeline Troubleshooting Guide

This guide covers common issues encountered when deploying and running the InstructLab pipeline on OpenShift AI, based on real deployment experience.

## Table of Contents

- [DSPA Deployment Issues](#dspa-deployment-issues)
- [Pipeline Submission Problems](#pipeline-submission-problems)
- [GPU and Node Scheduling](#gpu-and-node-scheduling)
- [Storage and PVC Issues](#storage-and-pvc-issues)
- [Model Serving Problems](#model-serving-problems)
- [Pipeline Execution Failures](#pipeline-execution-failures)
- [Authentication and Secrets](#authentication-and-secrets)

## DSPA Deployment Issues

### Issue: DSPA Components Not Starting

**Symptoms:**
```bash
oc get pods -n petloan-instructlab
# Shows pods in CrashLoopBackOff or Pending state
```

**Common Causes:**
1. **Missing Operators**: OpenShift AI operators not installed
2. **Resource Constraints**: Insufficient cluster resources
3. **RBAC Issues**: Service account lacks permissions

**Solutions:**

```bash
# 1. Check OpenShift AI operator status
oc get csv -n redhat-ods-operator
oc get pods -n redhat-ods-applications

# 2. Verify resource availability
oc describe nodes | grep -A 5 "Allocated resources"

# 3. Check DSPA status for detailed errors
oc describe dspa dspa -n petloan-instructlab

# 4. Recreate DSPA if needed
oc delete dspa dspa -n petloan-instructlab
oc apply -f 01-dspa.yaml
```

### Issue: MinIO Connectivity Problems

**Symptoms:**
```
DSPA condition: ObjectStoreAvailable = False
Error: context deadline exceeded
```

**Solutions:**

```bash
# 1. Check MinIO pod and service
oc get pods -n petloan-instructlab | grep minio
oc get svc minio-dspa -n petloan-instructlab

# 2. Test MinIO connectivity
oc run debug-pod --image=curlimages/curl --rm -it -- /bin/sh
# Inside pod:
curl http://minio-dspa.petloan-instructlab.svc.cluster.local:9000

# 3. Verify MinIO credentials
oc get secret ds-pipeline-s3-dspa -n petloan-instructlab -o yaml
oc describe secret ds-pipeline-s3-dspa -n petloan-instructlab

# 4. Restart MinIO pod
oc delete pod -l app=minio-dspa -n petloan-instructlab
```

## Pipeline Submission Problems

### Issue: 403 Forbidden on Pipeline Submission

**Symptoms:**
```
❌ Pipeline submission failed: Status: 403
Response: Access denied or HTML login page
```

**Solutions:**

**Method 1: Use Port Forwarding (Recommended)**
```bash
# Start port forwarding in separate terminal
oc port-forward -n petloan-instructlab svc/ds-pipeline-dspa 8888:8888

# Submit pipeline (default mode)
python3 submit_pipeline.py
```

**Method 2: Refresh OpenShift Token**
```bash
# Re-login to OpenShift
oc login --web
oc project petloan-instructlab

# Verify token
oc whoami -t
```

### Issue: Pipeline Not Found

**Symptoms:**
```
❌ Could not find InstructLab pipeline
```

**Solutions:**

```bash
# 1. Check if DSPA managed pipelines are enabled
oc describe dspa dspa -n petloan-instructlab | grep -i pipeline

# 2. Verify InstructLab pipeline is registered
# Via port-forward API call:
curl -k https://localhost:8888/apis/v2beta1/pipelines \
  -H "Authorization: Bearer $(oc whoami -t)"

# 3. If missing, check DSPA logs
oc logs -l app=ds-pipeline-dspa -n petloan-instructlab
```

## GPU and Node Scheduling

### Issue: Pods Pending Due to GPU Taints

**Symptoms:**
```bash
oc get pods | grep Pending
oc describe pod <pod-name>
# Shows: node(s) had taint that the pod didn't tolerate
```

**Root Cause:**
GPU nodes have taints that require explicit tolerations in pod specs.

**Solutions:**

The pipeline parameters include GPU tolerations:
```yaml
train_tolerations:
  - key: "nvidia.com/gpu"
    operator: "Equal" 
    value: "true"
    effect: "NoSchedule"
```

**Verify GPU Node Configuration:**
```bash
# Check GPU nodes and taints
oc get nodes -l nvidia.com/gpu.machine
oc describe node <gpu-node-name> | grep -A 5 Taints

# Expected taint: nvidia.com/gpu=true:NoSchedule
```

### Issue: GPU Resources Not Available

**Symptoms:**
```
insufficient nvidia.com/gpu resources
```

**Solutions:**

```bash
# 1. Check GPU availability on nodes
oc describe nodes | grep -A 10 "nvidia.com/gpu"

# 2. Check existing GPU usage
oc get pods -A -o yaml | grep -A 3 "nvidia.com/gpu"

# 3. Verify GPU operator is running
oc get pods -n nvidia-gpu-operator

# 4. Check node labels
oc get nodes --show-labels | grep nvidia
```

## Storage and PVC Issues

### Issue: PVC Stuck in Pending

**Symptoms:**
```bash
oc get pvc
# Shows PersistentVolumeClaim in Pending state
```

**Common Causes:**

1. **Unsupported Access Mode**: `ReadWriteMany` on EBS storage classes
2. **Missing Storage Class**: No storage class specified
3. **Zone Mismatch**: PVC and pod in different availability zones

**Solutions:**

```bash
# 1. Check available storage classes
oc get storageclass

# 2. Fix access mode (use ReadWriteOnce for EBS)
# In PVC spec:
spec:
  accessModes:
    - ReadWriteOnce  # Not ReadWriteMany
  storageClassName: gp3

# 3. For zone-specific issues, specify zone in node selector:
train_node_selectors:
  topology.kubernetes.io/zone: "us-east-1a"
```

### Issue: Pipeline Fails with Storage Mount Errors

**Symptoms:**
```
Error: failed to mount volume
VolumeMount: /workspace/taxonomy not found
```

**Solutions:**

The pipeline requires `ReadWriteOnce` storage. Update pipeline parameters:
```yaml
k8s_storage_class_name: "gp3"
k8s_storage_size: "50Gi"
```

## Model Serving Problems

### Issue: Model Pods Crashing

**Symptoms:**
```bash
oc get pods | grep -E "(teacher|judge)"
# Shows CrashLoopBackOff
```

**Common Causes:**

1. **Invalid Command Arguments**: Extra arguments in container args
2. **Missing Model Files**: PVC doesn't contain proper model files
3. **Resource Constraints**: Insufficient GPU/memory

**Solutions:**

```bash
# 1. Check pod logs
oc logs <model-pod-name> -f

# 2. Verify model files in PVC
oc run debug-pod --image=busybox --rm -it \
  --overrides='{"spec":{"volumes":[{"name":"model-vol","persistentVolumeClaim":{"claimName":"<pvc-name>"}}],"containers":[{"name":"debug","image":"busybox","volumeMounts":[{"name":"model-vol","mountPath":"/models"}],"stdin":true,"tty":true}]}}' \
  -- /bin/sh
# Inside pod: ls -la /models/model/

# 3. Fix deployment args (common issue)
# Remove extra numeric args like '4 4' from vLLM container args
```

### Issue: Model Service Returns 404

**Symptoms:**
```
HTTP Request: POST http://model-service:8000/v1/chat/completions
Response: 404 Not Found
```

**Solutions:**

```bash
# 1. Check service endpoint configuration
oc get svc -n petloan-instructlab | grep -E "(teacher|judge)"

# 2. Port mismatch - ensure service port matches container port
# Judge service example:
spec:
  ports:
  - port: 8000      # External port
    targetPort: 8001  # Container port (must match)

# 3. Test service connectivity
oc port-forward svc/<service-name> 8000:8000
curl http://localhost:8000/health
```

## Pipeline Execution Failures

### Issue: Pipeline Fails at SDG Phase

**Symptoms:**
```
Error in synthetic data generation
Teacher model connection failed
```

**Solutions:**

```bash
# 1. Verify teacher model is ready
oc get pods -l app=mixtral-teacher
oc logs <teacher-pod> | tail -20

# 2. Check teacher secret configuration
oc get secret teacher-secret -o yaml
# Ensure keys: api_token, model_name, endpoint

# 3. Test teacher model directly
oc port-forward svc/mixtral-teacher 8000:8000
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer teacher-model-key" \
  -H "Content-Type: application/json" \
  -d '{"model": "Mixtral-8x7B-Instruct-v0.1", "messages": [{"role": "user", "content": "Hello"}]}'
```

### Issue: Pipeline Fails with Base Model Error

**Symptoms:**
```
Error: Unable to load base model
Invalid model specification
```

**Solutions:**

Use tested base model configurations:
```python
# Working base models:
"sdg_base_model": "microsoft/DialoGPT-medium"  # For testing
# OR
"sdg_base_model": "registry.redhat.io/rhelai1/granite-7b-starter"  # For production
```

## Authentication and Secrets

### Issue: Secret Key Mismatches

**Symptoms:**
```
KeyError: 'api_key' not found in secret
Secret reference failed
```

**Solutions:**

Ensure secret keys match pipeline expectations:

```yaml
# teacher-secret
stringData:
  api_token: "teacher-model-key"     # NOT api_key
  model_name: "Mixtral-8x7B-Instruct-v0.1"
  endpoint: "http://mixtral-teacher.petloan-instructlab.svc.cluster.local:8000/v1"

# judge-secret  
stringData:
  api_token: "judge-model-key"       # NOT api_key
  model_name: "Prometheus-8x7B-v2.0"
  endpoint: "http://prometheus-judge.petloan-instructlab.svc.cluster.local:8001/v1"
```

### Issue: Git Repository Access Denied

**Symptoms:**
```
Error cloning repository
Authentication failed
```

**Solutions:**

```bash
# 1. Update taxonomy-repo-secret
oc create secret generic taxonomy-repo-secret \
  --from-literal=username="your-github-username" \
  --from-literal=password="ghp_your-personal-access-token" \
  -n petloan-instructlab

# 2. Verify repository is accessible
git clone https://github.com/cnuland/hello-chris-dev-taxonomy.git
```

## General Debugging Commands

### Quick Status Check
```bash
# Overall cluster status
oc get pods -n petloan-instructlab
oc get pvc -n petloan-instructlab  
oc get svc -n petloan-instructlab
oc describe dspa dspa -n petloan-instructlab

# Pipeline runs
oc get pods | grep instructlab
oc logs <pipeline-pod> -f

# Model services
oc get pods | grep -E "(teacher|judge)"
oc logs <model-pod> | tail -20
```

### Resource Monitoring
```bash
# Node resources
oc top nodes
oc describe node <gpu-node> | grep -A 10 "Allocated resources"

# Pod resources  
oc top pods -n petloan-instructlab
oc describe pod <pod-name> | grep -A 5 "Requests:"
```

### Network Debugging
```bash
# Test service connectivity
oc run curl-debug --image=curlimages/curl --rm -it -- /bin/sh
# Inside pod:
nslookup mixtral-teacher.petloan-instructlab.svc.cluster.local
curl http://mixtral-teacher.petloan-instructlab.svc.cluster.local:8000/health
```

## Success Indicators

### Pipeline Running Successfully
- ✅ DSPA components all in "Running" state
- ✅ Teacher and judge models responding to health checks
- ✅ Pipeline progresses past prerequisite checks
- ✅ SDG pod scheduled on GPU node with proper tolerations  
- ✅ Taxonomy repository cloned and processed
- ✅ Synthetic data generation initiates

### Ready for Production
- ✅ Model registry service deployed and accessible
- ✅ Multi-worker training configuration tested
- ✅ Persistent volumes properly configured
- ✅ Authentication and secrets validated
- ✅ Resource requests match cluster capacity

---

This troubleshooting guide is based on real deployment experience. For additional issues, check the OpenShift and InstructLab documentation or OpenShift AI operator logs.
