#!/usr/bin/env python3
"""
InstructLab Pipeline Submission Script

This script submits a pipeline run to the DSPA InstructLab pipeline.
It supports both direct API access (via port-forwarding) and OAuth route access.
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
    """Submit an InstructLab pipeline run."""
    
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
    
    # Default pipeline parameters - tested and working configuration
    default_params = {
        # Required parameters
        "output_model_name": "fine-tuned-granite-7b",
        # Model registry parameters - empty values to disable registry checks
        "output_model_registry_api_url": "",  # Empty to disable model registry
        "output_model_registry_name": "",  # Empty to disable model registry
        "output_model_version": "",  # Empty to disable model registry
        "output_oci_model_uri": "",  # Empty to skip OCI model output
        "output_oci_registry_secret": "oci-output-push-secret",
        "sdg_base_model": "oci://registry.redhat.io/rhoai/granite-7b-starter",  # OCI format for base model
        "sdg_repo_url": "https://github.com/cnuland/hello-chris-dev-taxonomy.git",
        "train_node_selectors": {},
        "train_tolerations": [
            {
                "key": "nvidia.com/gpu",
                "operator": "Equal",
                "value": "true",
                "effect": "NoSchedule"
            }
        ],
        
        # Required SDG and training parameters
        "sdg_teacher_secret": "teacher-secret",
        "sdg_repo_secret": "taxonomy-repo-secret",
        "eval_judge_secret": "judge-secret",
        "train_gpu_identifier": "nvidia.com/gpu",
        "eval_gpu_identifier": "nvidia.com/gpu",
        "k8s_storage_class_name": "gp3",  # Required for EBS volumes
        "k8s_storage_size": "50Gi",
        
        # Production-ready parameters
        "sdg_scale_factor": 30,  # Generate more synthetic data
        "train_num_epochs_phase_1": 7,  # Multi-phase training
        "train_num_epochs_phase_2": 10,
        "train_effective_batch_size_phase_1": 3840,
        "train_effective_batch_size_phase_2": 3840,
        "train_learning_rate_phase_1": 2e-6,  # Conservative learning rates
        "train_learning_rate_phase_2": 1e-6,
        "train_cpu_per_worker": "8",
        "train_memory_per_worker": "32Gi",
        "train_gpu_per_worker": 1,
        "train_num_workers": 4,  # Multi-worker training
        "sdg_batch_size": 10,  # Balanced batch size for SDG
        "sdg_num_workers": 4,
        "mt_bench_merge_system_user_message": False,
        "final_eval_merge_system_user_message": False,
        "mt_bench_max_workers": "auto",
        "final_eval_max_workers": "auto",
        "final_eval_batch_size": "auto",
        "final_eval_few_shots": 5,
    }
    
    # Override with custom parameters if provided
    if custom_params:
        default_params.update(custom_params)
    
    # Create pipeline run payload
    payload = {
        "display_name": "instructlab-pipeline-run",
        "description": "InstructLab SDG and Training Pipeline Run",
        "pipeline_version_reference": {
            "pipeline_id": pipeline_id,
            "pipeline_version_id": version_id
        },
        "runtime_config": {
            "parameters": default_params
        }
    }
    
    # Submit the run
    print("🚀 Submitting pipeline run...")
    url = f"{dspa_url}/apis/v2beta1/runs"
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), verify=False)
        
        if response.status_code in [200, 201]:
            result = response.json()
            run_id = result.get('run_id', 'unknown')
            print(f"✅ Pipeline run submitted successfully!")
            print(f"   Run ID: {run_id}")
            print(f"   Display Name: {result.get('display_name')}")
            
            # Print monitoring commands
            print("\n📊 Monitor your pipeline run:")
            print(f"   DSPA Route: {dspa_url.replace('localhost:8888', get_dspa_info(namespace).split('://')[-1] if not use_port_forward else 'localhost:8888')}")
            print(f"   CLI: oc get pods -n {namespace} | grep instructlab")
            
            return True
        else:
            print(f"❌ Pipeline submission failed:")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error submitting pipeline: {e}")
        return False

def main():
    """Main function with command line argument parsing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Submit InstructLab Pipeline Run')
    parser.add_argument('--namespace', '-n', default='petloan-instructlab',
                       help='Namespace where DSPA is deployed')
    parser.add_argument('--route', action='store_true',
                       help='Use OAuth route instead of port-forward')
    parser.add_argument('--repo-url', 
                       help='Override taxonomy repository URL')
    parser.add_argument('--base-model',
                       help='Override base model')
    parser.add_argument('--output-model-name',
                       help='Override output model name')
    
    args = parser.parse_args()
    
    # Build custom parameters from arguments
    custom_params = {}
    if args.repo_url:
        custom_params['sdg_repo_url'] = args.repo_url
    if args.base_model:
        custom_params['sdg_base_model'] = args.base_model
    if args.output_model_name:
        custom_params['output_model_name'] = args.output_model_name
    
    # Submit pipeline
    success = submit_pipeline(
        namespace=args.namespace,
        use_port_forward=not args.route,
        custom_params=custom_params if custom_params else None
    )
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
