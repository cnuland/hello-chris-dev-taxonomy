#!/usr/bin/env python3
"""
InstructLab Pipeline Submission Script - COMPLETE MODEL TRAINING VERSION

This script submits an optimized pipeline run designed to complete the full model training
process including both training phases and model evaluation.
"""

import os
import sys
import requests
import json
import yaml
import urllib3
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings when using self-signed certificates
urllib3.disable_warnings(InsecureRequestWarning)

def get_openshift_token():
    """Extract OpenShift token from kubeconfig."""
    token_path = os.path.expanduser("~/.kube/config")
    try:
        with open(token_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Find the current context
        current_context = config.get('current-context')
        if not current_context:
            return None
            
        # Find the user for the current context
        for context in config.get('contexts', []):
            if context['name'] == current_context:
                user_name = context['context']['user']
                break
        else:
            return None
            
        # Find the token for the user
        for user in config.get('users', []):
            if user['name'] == user_name and 'token' in user['user']:
                return user['user']['token']
                
    except Exception as e:
        print(f"Error reading kubeconfig: {e}")
    return None

def get_dspa_info(namespace):
    """Get DSPA route and pipeline information."""
    # Get DSPA route
    cmd = f"oc get route ds-pipeline-dspa -n {namespace} -o jsonpath='{{.spec.host}}' 2>/dev/null"
    try:
        route = os.popen(cmd).read().strip()
        dspa_route = f"https://{route}" if route else None
    except Exception:
        dspa_route = None
    
    return dspa_route

def get_pipeline_info(dspa_url, headers):
    """Get pipeline ID and version ID from DSPA API."""
    try:
        # List pipelines
        pipelines_url = f"{dspa_url}/apis/v2beta1/pipelines"
        response = requests.get(pipelines_url, headers=headers, verify=False)
        
        if response.status_code == 200:
            pipelines = response.json()
            for pipeline in pipelines.get('pipelines', []):
                if pipeline.get('display_name') == 'InstructLab':
                    pipeline_id = pipeline.get('pipeline_id')
                    
                    # Get pipeline versions
                    versions_url = f"{dspa_url}/apis/v2beta1/pipelines/{pipeline_id}/versions"
                    versions_response = requests.get(versions_url, headers=headers, verify=False)
                    
                    if versions_response.status_code == 200:
                        versions = versions_response.json()
                        if versions.get('pipeline_versions'):
                            # Use the first version
                            version_id = versions['pipeline_versions'][0].get('pipeline_version_id')
                            return pipeline_id, version_id
        
    except Exception as e:
        print(f"Error getting pipeline info: {e}")
    
    return None, None

def submit_pipeline(namespace, use_port_forward=True, custom_params=None):
    """Submit an optimized InstructLab pipeline run for complete model training."""
    
    # Get OpenShift token
    token = get_openshift_token()
    if not token:
        print("❌ OpenShift token not found. Please log in to OpenShift with 'oc login'")
        return False
    
    # Set DSPA URL
    if use_port_forward:
        print("🔗 Using port-forwarded connection (recommended)")
        print("   Make sure port-forwarding is active: oc port-forward -n petloan-instructlab svc/ds-pipeline-dspa 8888:8888")
        dspa_url = "https://localhost:8888"
    else:
        print("🔗 Using OAuth route connection")
        dspa_url = get_dspa_info(namespace)
        if not dspa_url:
            print("❌ Could not get DSPA route. Try using port-forward mode.")
            return False
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    # Get pipeline and version IDs
    print("📋 Getting pipeline information...")
    pipeline_id, version_id = get_pipeline_info(dspa_url, headers)
    
    if not pipeline_id or not version_id:
        print("❌ Could not find InstructLab pipeline. Make sure it's registered in DSPA.")
        return False
    
    print(f"✅ Found InstructLab pipeline: {pipeline_id[:8]}...")
    print(f"✅ Using version: {version_id[:8]}...")
    
    # OPTIMIZED pipeline parameters for COMPLETE model training
    complete_training_params = {
        # Model output configuration
        "output_model_name": "fine-tuned-granite-7b-complete",
        
        # Disable model registry and OCI output to avoid blocking issues
        "output_model_registry_api_url": "",  
        "output_model_registry_name": "",  
        "output_model_version": "",  
        "output_oci_model_uri": "",  
        "output_oci_registry_secret": "oci-output-push-secret",
        
        # Base model and repository
        "sdg_base_model": "oci://registry.redhat.io/rhoai/granite-7b-starter",
        "sdg_repo_url": "https://github.com/cnuland/hello-chris-dev-taxonomy.git",
        
        # RELAXED node selection - remove restrictive GPU node selector
        "train_node_selectors": {},  # Empty to allow scheduling on any available nodes
        "train_tolerations": [
            {
                "key": "nvidia.com/gpu",
                "operator": "Equal", 
                "value": "true",
                "effect": "NoSchedule"
            }
        ],
        
        # Required secrets
        "sdg_teacher_secret": "teacher-secret",
        "sdg_repo_secret": "taxonomy-repo-secret", 
        "eval_judge_secret": "judge-secret",
        
        # GPU configuration
        "train_gpu_identifier": "nvidia.com/gpu",
        "eval_gpu_identifier": "nvidia.com/gpu",
        
        # OPTIMIZED storage configuration - use standard storage class
        "k8s_storage_class_name": "gp3",
        "k8s_storage_size": "50Gi",
        
        # Realistic production training parameters
        "sdg_scale_factor": 5,  # Generate sufficient training data
        
        # Two-phase training with meaningful epochs
        "train_num_epochs_phase_1": 2,  # Knowledge phase
        "train_num_epochs_phase_2": 3,  # Skills phase  
        "train_effective_batch_size_phase_1": 256,  # Reasonable batch sizes
        "train_effective_batch_size_phase_2": 256,
        "train_learning_rate_phase_1": 2e-5,  # Conservative learning rates
        "train_learning_rate_phase_2": 1e-5,
        
        # Resource allocation - balanced for completion
        "train_cpu_per_worker": "6",
        "train_memory_per_worker": "24Gi", 
        "train_gpu_per_worker": 1,
        "train_num_workers": 1,  # Single node to avoid scheduling complexity
        
        # SDG parameters
        "sdg_batch_size": 4,  
        "sdg_num_workers": 4,
        
        # Evaluation parameters
        "mt_bench_merge_system_user_message": False,
        "final_eval_merge_system_user_message": False,
        "mt_bench_max_workers": "2",  
        "final_eval_max_workers": "2",
        "final_eval_batch_size": "4",  
        "final_eval_few_shots": 2,
        
        # Training optimization
        "train_num_warmup_steps_phase_1": 100,  # Reduced warmup
        "train_num_warmup_steps_phase_2": 100,
        "train_save_samples": 50000,  # Save checkpoints more frequently
        "train_seed": 42,
        "train_max_batch_len": 4096,  # Optimized for A100 GPUs
        
        # SDG optimization
        "sdg_max_batch_len": 4096,
        "sdg_sample_size": 1.0,  # Use full sample size
        "sdg_pipeline": "/usr/share/instructlab/sdg/pipelines/full",  # Use full pipeline for better quality
    }
    
    # Override with custom parameters if provided
    if custom_params:
        complete_training_params.update(custom_params)
    
    # Create pipeline run payload
    payload = {
        "display_name": "instructlab-complete-training-run",
        "description": "InstructLab Complete Model Training Pipeline - Optimized for Full Completion",
        "pipeline_version_reference": {
            "pipeline_id": pipeline_id,
            "pipeline_version_id": version_id
        },
        "runtime_config": {
            "parameters": complete_training_params
        }
    }
    
    # Submit the run
    print("🚀 Submitting COMPLETE TRAINING pipeline run...")
    print("   Optimized for full model training completion")
    print("   Two-phase training: Knowledge → Skills → Evaluation")
    url = f"{dspa_url}/apis/v2beta1/runs"
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), verify=False)
        
        if response.status_code in [200, 201]:
            result = response.json()
            run_id = result.get('run_id', 'unknown')
            print(f"✅ COMPLETE TRAINING Pipeline submitted successfully!")
            print(f"   Run ID: {run_id}")
            print(f"   Display Name: {result.get('display_name')}")
            
            print("\n🎯 PIPELINE OPTIMIZATIONS APPLIED:")
            print("   • Relaxed node selectors for better scheduling")
            print("   • Single worker configuration for stability")
            print("   • Realistic training epochs (2+3 phases)")
            print("   • Balanced resource allocation")
            print("   • Full SDG pipeline for quality data")
            print("   • Disabled registry/OCI to avoid blocking")
            
            print("\n📊 Monitor your complete training pipeline:")
            print(f"   kubectl get workflows -n {namespace}")
            print(f"   kubectl get pods -n {namespace} | grep instructlab")
            print(f"   kubectl get pytorchjobs -n {namespace}")
            
            return True, run_id
        else:
            print(f"❌ Pipeline submission failed:")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False, None
            
    except Exception as e:
        print(f"❌ Error submitting pipeline: {e}")
        return False, None

def monitor_pipeline(namespace, run_id=None):
    """Monitor the pipeline execution until completion."""
    print(f"\n🔍 Starting pipeline monitoring...")
    
    import time
    
    # Find the most recent workflow if run_id not provided
    if not run_id:
        result = os.popen(f"kubectl get workflows -n {namespace} --sort-by=.metadata.creationTimestamp -o jsonpath='{{.items[-1].metadata.name}}'").read().strip()
        workflow_name = result if result else None
    else:
        # Find workflow by run_id in labels
        result = os.popen(f"kubectl get workflows -n {namespace} -l pipeline/runid={run_id} -o jsonpath='{{.items[0].metadata.name}}'").read().strip()
        workflow_name = result if result else None
    
    if not workflow_name:
        print("❌ Could not find workflow to monitor")
        return False
    
    print(f"📋 Monitoring workflow: {workflow_name}")
    
    monitoring_duration = 0
    max_monitoring_time = 4 * 60 * 60  # 4 hours max monitoring
    check_interval = 30  # Check every 30 seconds
    
    last_status = None
    last_progress = None
    
    while monitoring_duration < max_monitoring_time:
        try:
            # Get workflow status
            status_cmd = f"kubectl get workflow {workflow_name} -n {namespace} -o jsonpath='{{.status.phase}}'"
            status = os.popen(status_cmd).read().strip()
            
            # Get workflow progress  
            progress_cmd = f"kubectl get workflow {workflow_name} -n {namespace} -o jsonpath='{{.status.progress}}'"
            progress = os.popen(progress_cmd).read().strip()
            
            # Get workflow message
            message_cmd = f"kubectl get workflow {workflow_name} -n {namespace} -o jsonpath='{{.status.message}}'"
            message = os.popen(message_cmd).read().strip()
            
            current_time = time.strftime("%H:%M:%S")
            
            # Print update if status or progress changed
            if status != last_status or progress != last_progress:
                print(f"\n[{current_time}] 📊 Pipeline Status Update:")
                print(f"   Status: {status}")
                print(f"   Progress: {progress}")
                if message:
                    print(f"   Message: {message}")
                
                # Check for completion
                if status in ["Succeeded", "Failed", "Error"]:
                    print(f"\n🏁 Pipeline completed with status: {status}")
                    if status == "Succeeded":
                        print("🎉 SUCCESS! Model training completed successfully!")
                        print(f"   Monitor trained model: kubectl get pods -n {namespace} | grep {workflow_name}")
                        return True
                    else:
                        print(f"❌ Pipeline failed with status: {status}")
                        if message:
                            print(f"   Error details: {message}")
                        return False
                
                last_status = status
                last_progress = progress
            
            # Check for active PyTorchJobs (training in progress)
            pytorch_jobs = os.popen(f"kubectl get pytorchjobs -n {namespace} --no-headers 2>/dev/null | wc -l").read().strip()
            if pytorch_jobs and int(pytorch_jobs) > 0:
                print(f"[{current_time}] 🏋️ Training in progress - {pytorch_jobs} PyTorchJobs active")
            
            time.sleep(check_interval)
            monitoring_duration += check_interval
            
        except KeyboardInterrupt:
            print(f"\n⏹️ Monitoring interrupted by user")
            return False
        except Exception as e:
            print(f"[{current_time}] ⚠️ Monitoring error: {e}")
            time.sleep(check_interval)
            monitoring_duration += check_interval
    
    print(f"\n⏰ Maximum monitoring time ({max_monitoring_time/3600:.1f} hours) reached")
    print(f"   Pipeline may still be running. Check manually with:")
    print(f"   kubectl get workflows -n {namespace}")
    return False

def main():
    """Main function with command line argument parsing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Submit Complete InstructLab Pipeline Run')
    parser.add_argument('--namespace', '-n', default='petloan-instructlab',
                       help='Namespace where DSPA is deployed')
    parser.add_argument('--route', action='store_true',
                       help='Use OAuth route instead of port-forward')
    parser.add_argument('--monitor', '-m', action='store_true',
                       help='Monitor the pipeline until completion')
    parser.add_argument('--repo-url', 
                       help='Override taxonomy repository URL')
    parser.add_argument('--base-model',
                       help='Override base model')
    parser.add_argument('--output-model-name',
                       help='Override output model name')
    
    args = parser.parse_args()
    
    print("🎯 COMPLETE MODEL TRAINING PIPELINE SUBMISSION")
    print("   This pipeline is optimized to complete full model training")
    print("   Including: SDG → Data Processing → Training Phase 1 & 2 → Evaluation")
    print()
    
    # Build custom parameters from arguments
    custom_params = {}
    if args.repo_url:
        custom_params['sdg_repo_url'] = args.repo_url
    if args.base_model:
        custom_params['sdg_base_model'] = args.base_model
    if args.output_model_name:
        custom_params['output_model_name'] = args.output_model_name
    
    # Submit pipeline
    success, run_id = submit_pipeline(
        namespace=args.namespace,
        use_port_forward=not args.route,
        custom_params=custom_params if custom_params else None
    )
    
    if not success:
        sys.exit(1)
    
    print("\n🎯 EXPECTED PIPELINE STAGES:")
    print("   1. ✅ Prerequisites & Validation")
    print("   2. 🔄 Synthetic Data Generation (SDG)")
    print("   3. 🔄 Data Processing & Preparation") 
    print("   4. 🏋️ Training Phase 1 (Knowledge)")
    print("   5. 🏋️ Training Phase 2 (Skills)")
    print("   6. 📊 Model Evaluation")
    print("   7. 🎉 Completion & Model Export")
    
    # Start monitoring if requested
    if args.monitor:
        print("\n🔍 Starting automatic monitoring...")
        success = monitor_pipeline(args.namespace, run_id)
        if success:
            print("\n🏆 COMPLETE SUCCESS! Your fine-tuned model is ready!")
        else:
            print("\n⚠️ Monitoring ended - check pipeline status manually")
    else:
        print(f"\n📋 To monitor manually:")
        print(f"   kubectl get workflows -n {args.namespace}")
        print(f"   kubectl logs -f <pod-name> -n {args.namespace}")

if __name__ == "__main__":
    main()
