# InstructLab Pipeline Quick Start Guide

Get your InstructLab pipeline running on OpenShift AI in under 30 minutes! This guide walks you through the essential steps to deploy and run the pipeline successfully.

## Prerequisites Check ✅

Before starting, ensure you have:

- [ ] **OpenShift 4.14+** cluster with cluster-admin access
- [ ] **OpenShift AI** operator installed
- [ ] **GPU nodes** (recommended) with NVIDIA GPU Operator
- [ ] **oc CLI** installed and logged in
- [ ] **Python 3.8+** with pip
- [ ] **Git** repository for taxonomy data

## 🚀 5-Minute Deployment

### 1. Clone and Navigate
```bash
git clone https://github.com/your-org/hello-chris-dev-taxonomy.git
cd hello-chris-dev-taxonomy/dspa-deployment
```

### 2. Quick Environment Check
```bash
# Check if you're logged in to OpenShift
oc whoami

# Verify OpenShift AI is installed
oc get csv -n redhat-ods-operator | grep rhods
```

### 3. Deploy DSPA Infrastructure
```bash
# Make scripts executable
chmod +x *.sh *.py

# Deploy everything
./deploy.sh
```

**Expected Output:**
```
🚀 Starting DSPA deployment...
📁 Creating namespace: petloan-instructlab  
🔧 Deploying service account and RBAC...
🔐 Deploying secrets...
🏗️ Deploying DSPA...
✅ DSPA deployment completed successfully!
```

### 4. Verify Installation
```bash
# Check pods (should all be Running)
oc get pods -n petloan-instructlab

# Check DSPA status (should be Ready)
oc describe dspa dspa -n petloan-instructlab | grep -A 5 Conditions
```

### 5. Submit Your First Pipeline
```bash
# Install Python dependencies
pip install -r requirements.txt

# Start port forwarding (in separate terminal)
oc port-forward -n petloan-instructlab svc/ds-pipeline-dspa 8888:8888

# Submit pipeline with working defaults
python3 submit_pipeline.py
```

**Success Indicators:**
```
✅ Pipeline run submitted successfully!
   Run ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
   Display Name: instructlab-pipeline-run

📊 Monitor your pipeline run:
   CLI: oc get pods -n petloan-instructlab | grep instructlab
```

## 📊 Monitor Your Pipeline

### Check Pipeline Status
```bash
# List running pipeline pods
oc get pods -n petloan-instructlab | grep instructlab

# Follow pipeline logs
oc logs -f <pipeline-pod-name> -n petloan-instructlab

# Check resource usage
oc top pods -n petloan-instructlab
```

### Pipeline Phases to Watch For:
1. **Prerequisites Check** ✅ - Validates configuration
2. **Synthetic Data Generation (SDG)** 🔄 - Creates training data
3. **Model Training** 🎯 - Fine-tunes the model
4. **Model Evaluation** 📈 - Assesses model quality

## 🔧 Common First-Run Issues

### Issue: Pod Stuck in Pending (GPU Nodes)
```bash
# Check if pod needs GPU but node has taints
oc describe pod <pod-name> | grep -A 5 Events

# Solution: GPU tolerations are already configured in submit_pipeline.py
```

### Issue: PVC Pending (Storage)
```bash
# Check PVC status
oc get pvc -n petloan-instructlab

# Solution: Pipeline uses gp3 storage class with ReadWriteOnce
```

### Issue: 403 Forbidden on Pipeline Submission
```bash
# Check if port-forwarding is active
curl -k https://localhost:8888/health

# Restart port-forwarding if needed
oc port-forward -n petloan-instructlab svc/ds-pipeline-dspa 8888:8888
```

## 🎯 Using Your Own Taxonomy

### Method 1: Public Repository
```bash
python3 submit_pipeline.py \
    --repo-url "https://github.com/your-org/your-taxonomy.git" \
    --output-model-name "your-custom-model"
```

### Method 2: Private Repository
```bash
# Update the taxonomy-repo-secret first (do NOT commit secrets to Git)
oc create secret generic taxonomy-repo-secret \
  --from-literal=username="your-github-username" \
  --from-literal=password="ghp_your-personal-access-token" \
  -n petloan-instructlab --dry-run=client -o yaml | oc apply -f -

# Then submit pipeline
python3 submit_pipeline.py --repo-url "https://github.com/your-org/private-taxonomy.git"
```

### Required Secrets (out-of-band)
Before running pipelines, create the following Kubernetes Secrets in the petloan-instructlab namespace:

- Taxonomy repo credentials (for private repos):
```bash
oc create secret generic taxonomy-repo-secret \
  --from-literal=username="<your-git-username>" \
  --from-literal=password="<your-git-token-or-password>" \
  -n petloan-instructlab --dry-run=client -o yaml | oc apply -f -
```

- S3/MinIO credentials (referenced by manifests as s3-credentials):
```bash
oc create secret generic s3-credentials \
  --from-literal=AWS_ACCESS_KEY_ID="<your-access-key-id>" \
  --from-literal=AWS_SECRET_ACCESS_KEY="<your-secret-access-key>" \
  --from-literal=AWS_DEFAULT_REGION="<your-region>" \
  -n petloan-instructlab --dry-run=client -o yaml | oc apply -f -
```

## ⚡ Production Deployment Tips

### 1. Scale Up Parameters
Edit `submit_pipeline.py` for production workloads:
```python
# In default_params section:
"sdg_scale_factor": 100,          # More synthetic data
"train_num_epochs_phase_1": 10,   # More training epochs  
"train_num_workers": 8,           # Multi-worker training
"train_gpu_per_worker": 2,        # More GPUs per worker
```

### 2. Deploy Local Models (Optional)
```bash
# Deploy teacher and judge models for better performance
oc apply -f ../examples/model-deployments/teacher-model-deployment.yaml
oc apply -f ../examples/model-deployments/judge-model-deployment.yaml
```

### 3. Resource Optimization
```bash
# Check node resources
oc top nodes

# Monitor GPU usage
oc describe nodes | grep -A 10 "nvidia.com/gpu"
```

## 📋 Success Checklist

After your first pipeline run, you should have:

- [ ] ✅ DSPA components running (3-4 pods)
- [ ] ✅ Pipeline submitted successfully (Run ID received)
- [ ] ✅ SDG phase initiated (taxonomy processed)
- [ ] ✅ Training pods scheduled on appropriate nodes
- [ ] ✅ Model artifacts generated in MinIO storage

## 🆘 Need Help?

### Quick Debug Commands
```bash
# Overall cluster health
oc get pods -n petloan-instructlab
oc describe dspa dspa -n petloan-instructlab

# Pipeline troubleshooting
oc get pods | grep instructlab
oc logs <pipeline-pod> | tail -50

# Storage and networking
oc get pvc -n petloan-instructlab
oc get svc -n petloan-instructlab
```

### Resources
- 📖 **Full Documentation**: See [README.md](README.md) for complete details
- 🔧 **Troubleshooting**: See [TROUBLESHOOTING.md](dspa-deployment/TROUBLESHOOTING.md) for common issues
- 🏗️ **Architecture**: See diagrams and detailed explanations in main README

### Support Channels
- **GitHub Issues**: Report bugs and feature requests
- **OpenShift AI Documentation**: For operator-specific issues
- **InstructLab Community**: For pipeline and taxonomy questions

---

🎉 **Congratulations!** You now have a working InstructLab pipeline. Your next step is to create your own taxonomy and start fine-tuning models for your specific use cases!

---

*This guide gets you from zero to running pipeline in ~30 minutes. For production deployments, please review the full documentation and security considerations.*
