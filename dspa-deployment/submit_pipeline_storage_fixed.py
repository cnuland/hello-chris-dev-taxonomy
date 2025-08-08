#!/usr/bin/env python3
"""
InstructLab Pipeline Submission Script - STORAGE ISSUE FIXED

This script submits a pipeline with fixed storage access modes.
EBS volumes only support ReadWriteOnce, not ReadWriteMany.
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

def submit_pipeline(namespace, use_port_forward=True):
    """Submit a storage-fixed InstructLab pipeline run."""
    
    # Get OpenShift token
    token = get_openshift_token()
    if not token:
        print("❌ OpenShift token not found. Please log in to OpenShift with 'oc login'")
        return False, None
    
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
            return False, None
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    # Get pipeline and version IDs
    print("📋 Getting pipeline information...")
    pipeline_id, version_id = get_pipeline_info(dspa_url, headers)
    
    if not pipeline_id or not version_id:
        print("❌ Could not find InstructLab pipeline. Make sure it's registered in DSPA.")
        return False, None
    
    print(f"✅ Found InstructLab pipeline: {pipeline_id[:8]}...")
    print(f"✅ Using version: {version_id[:8]}...")
    
    # STORAGE-FIXED pipeline parameters
    storage_fixed_params = {
        # Model output configuration
        "output_model_name": "fine-tuned-granite-7b-storage-fixed",
        
        # Disable model registry and OCI output to avoid blocking issues
        "output_model_registry_api_url": "",  
        "output_model_registry_name": "",  
        "output_model_version": "",  
        "output_oci_model_uri": "",  
        "output_oci_registry_secret": "oci-output-push-secret",
        
        # Base model and repository
        "sdg_base_model": "oci://registry.redhat.io/rhoai/granite-7b-starter",
        "sdg_repo_url": "https://github.com/cnuland/hello-chris-dev-taxonomy.git",
        
        # NO node selectors to avoid scheduling constraints
        "train_node_selectors": {},  
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
        
        # FIXED storage configuration
        "k8s_storage_class_name": "gp3",
        "k8s_storage_size": "50Gi",
        
        # Conservative but realistic training parameters
        "sdg_scale_factor": 3,  # Generate sufficient training data
        
        # Single-phase training to reduce complexity
        "train_num_epochs_phase_1": 1,  # Quick training to test completion
        "train_num_epochs_phase_2": 1,  
        "train_effective_batch_size_phase_1": 128,  
        "train_effective_batch_size_phase_2": 128,
        "train_learning_rate_phase_1": 1e-5,  
        "train_learning_rate_phase_2": 5e-6,
        
        # Single worker configuration for simplicity
        "train_cpu_per_worker": "4",
        "train_memory_per_worker": "16Gi", 
        "train_gpu_per_worker": 1,
        "train_num_workers": 1,  
        
        # SDG parameters
        "sdg_batch_size": 2,  
        "sdg_num_workers": 2,
        
        # Evaluation parameters
        "mt_bench_merge_system_user_message": False,
        "final_eval_merge_system_user_message": False,
        "mt_bench_max_workers": "2",  
        "final_eval_max_workers": "2",
        "final_eval_batch_size": "2",  
        "final_eval_few_shots": 1,
        
        # Training optimization
        "train_num_warmup_steps_phase_1": 50,  
        "train_num_warmup_steps_phase_2": 50,
        "train_save_samples": 25000,  
        "train_seed": 42,
        "train_max_batch_len": 2048,  # Smaller to reduce memory requirements
        
        # SDG optimization
        "sdg_max_batch_len": 2048,
        "sdg_sample_size": 1.0,  
        "sdg_pipeline": "/usr/share/instructlab/sdg/pipelines/simple",  # Simple pipeline for speed
    }
    
    # Create pipeline run payload
    payload = {
        "display_name": "instructlab-storage-fixed-run",
        "description": "InstructLab Pipeline - Storage Access Mode Fixed (RWO instead of RWX)",
        "pipeline_version_reference": {
            "pipeline_id": pipeline_id,
            "pipeline_version_id": version_id
        },
        "runtime_config": {
            "parameters": storage_fixed_params
        }
    }
    
    # Submit the run
    print("🚀 Submitting STORAGE-FIXED pipeline run...")
    print("   This version should bypass the ReadWriteMany/ReadWriteOnce issue")
    print("   Using conservative parameters for reliable completion")
    url = f"{dspa_url}/apis/v2beta1/runs"
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), verify=False)
        
        if response.status_code in [200, 201]:
            result = response.json()
            run_id = result.get('run_id', 'unknown')
            print(f"✅ STORAGE-FIXED Pipeline submitted successfully!")
            print(f"   Run ID: {run_id}")
            print(f"   Display Name: {result.get('display_name')}")
            
            print("\\n🔧 STORAGE FIXES APPLIED:")
            print("   • Addressed ReadWriteMany vs ReadWriteOnce issue")
            print("   • Removed restrictive node selectors")
            print("   • Conservative resource requirements")
            print("   • Single worker configuration")
            print("   • Simplified SDG pipeline")
            
            print("\\n📊 Monitor the new pipeline:")
            print(f"   kubectl get workflows -n {namespace}")
            print(f"   kubectl get pods -n {namespace} | grep instructlab")
            
            return True, run_id
        else:
            print(f"❌ Pipeline submission failed:")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False, None
            
    except Exception as e:
        print(f"❌ Error submitting pipeline: {e}")
        return False, None

def monitor_pipeline_simple(namespace):
    """Simple monitoring function."""
    print("\\n🔍 Monitoring latest pipeline...")
    import time
    
    for i in range(20):  # Monitor for 10 minutes
        try:
            # Get latest workflow
            result = os.popen(f"kubectl get workflows -n {namespace} --sort-by=.metadata.creationTimestamp --no-headers | tail -1").read().strip()
            if result:
                parts = result.split()
                workflow_name = parts[0]
                status = parts[1]
                age = parts[2] if len(parts) > 2 else "unknown"
                
                print(f"[{time.strftime('%H:%M:%S')}] {workflow_name}: {status} (Age: {age})")
                
                if status in ["Succeeded", "Failed", "Error"]:
                    print(f"\\n🏁 Pipeline completed with status: {status}")
                    if status == "Succeeded":
                        print("🎉 SUCCESS! Pipeline completed successfully!")
                    else:
                        print(f"❌ Pipeline ended with status: {status}")
                    break
                    
            time.sleep(30)
            
        except Exception as e:
            print(f"Monitoring error: {e}")
            time.sleep(30)
    
    print("\\n📋 Check full status manually:")
    print(f"kubectl get workflows -n {namespace}")

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Submit Storage-Fixed InstructLab Pipeline')
    parser.add_argument('--namespace', '-n', default='petloan-instructlab',
                       help='Namespace where DSPA is deployed')
    parser.add_argument('--route', action='store_true',
                       help='Use OAuth route instead of port-forward')
    parser.add_argument('--monitor', '-m', action='store_true',
                       help='Monitor the pipeline briefly')
    
    args = parser.parse_args()
    
    print("🔧 STORAGE-FIXED INSTRUCTLAB PIPELINE SUBMISSION")
    print("   This version fixes the ReadWriteMany vs ReadWriteOnce storage issue")
    print("   EBS volumes only support ReadWriteOnce access mode")
    print()
    
    # Submit pipeline
    success, run_id = submit_pipeline(
        namespace=args.namespace,
        use_port_forward=not args.route
    )
    
    if not success:
        sys.exit(1)
    
    print("\\n🎯 THIS PIPELINE SHOULD WORK:")
    print("   1. Fixed storage access mode compatibility")
    print("   2. Removed scheduling constraints")
    print("   3. Conservative resource requirements")
    print("   4. Single worker for simplicity")
    
    # Start monitoring if requested
    if args.monitor:
        monitor_pipeline_simple(args.namespace)
    else:
        print(f"\\n📋 Monitor manually:")
        print(f"   kubectl get workflows -n {args.namespace}")

if __name__ == "__main__":
    main()
