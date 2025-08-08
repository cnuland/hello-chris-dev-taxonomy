#!/usr/bin/env python3

import argparse
import json
import time
import requests
import subprocess
import sys
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def get_bearer_token():
    """Extract bearer token from oc command"""
    try:
        result = subprocess.run(['oc', 'whoami', '--show-token'], 
                              capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error getting token: {e}")
        sys.exit(1)

def get_dspa_route(namespace="petloan-instructlab"):
    """Get the Data Science Pipeline Application route"""
    try:
        result = subprocess.run(['oc', 'get', 'route', 'ds-pipeline-dspa', 
                               '-n', namespace, '-o', 'jsonpath={.spec.host}'], 
                              capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error getting route: {e}")
        sys.exit(1)

def get_pipeline_info(dspa_host, token, namespace="petloan-instructlab"):
    """Get pipeline information"""
    url = f"https://{dspa_host}/apis/v1beta1/pipelines"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    params = {
        'resource_reference_key.type': 'NAMESPACE',
        'resource_reference_key.id': namespace
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, verify=False)
        response.raise_for_status()
        data = response.json()
        
        if 'pipelines' in data and data['pipelines']:
            # Look for InstructLab pipeline
            for pipeline in data['pipelines']:
                if 'instructlab' in pipeline.get('display_name', '').lower():
                    print(f"Found InstructLab pipeline: {pipeline['display_name']}")
                    return pipeline['id']
            
            # If no InstructLab pipeline found, use the first one
            pipeline = data['pipelines'][0]
            print(f"Using pipeline: {pipeline['display_name']}")
            return pipeline['id']
        else:
            print("No pipelines found")
            return None
    except Exception as e:
        print(f"Error getting pipeline info: {e}")
        return None

def submit_pipeline_run(dspa_host, token, pipeline_id, namespace="petloan-instructlab"):
    """Submit pipeline run with NFS storage configuration"""
    
    url = f"https://{dspa_host}/apis/v1beta1/runs"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Pipeline parameters optimized for completion with NFS storage
    pipeline_spec = {
        "display_name": f"InstructLab-Complete-NFS-{int(time.time())}",
        "description": "Complete InstructLab pipeline run with NFS storage for RWX volumes",
        "pipeline_spec": {
            "pipeline_id": pipeline_id,
            "parameters": [
                {"name": "model_to_train", "value": "instructlab/granite-7b-lab"},
                {"name": "num_epochs", "value": "10"},
                {"name": "learning_rate", "value": "0.0002"},
                {"name": "num_instructions_to_generate", "value": "100"},
                {"name": "taxonomy_repo_branch", "value": "main"},
                {"name": "mmlu_branch", "value": "main"},
                {"name": "mt_bench_branch", "value": "main"},
                {"name": "storage_class_name", "value": "nfs-manual"},  # Use NFS storage
                {"name": "pipeline_output_directory", "value": "/tmp/instructlab"},
                {"name": "enable_lora", "value": "true"},
                {"name": "lora_rank", "value": "4"},
                {"name": "lora_alpha", "value": "32"},
                {"name": "batch_size", "value": "1"},
                {"name": "gradient_accumulation_steps", "value": "4"},
                {"name": "warmup_steps", "value": "10"},
                {"name": "save_samples", "value": "0"},
                {"name": "log_level", "value": "INFO"},
                {"name": "max_batch_len", "value": "60000"},
                {"name": "seed", "value": "42"}
            ]
        },
        "resource_references": [
            {
                "key": {
                    "type": "NAMESPACE",
                    "id": namespace
                },
                "relationship": "OWNER"
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=pipeline_spec, verify=False)
        response.raise_for_status()
        run_data = response.json()
        
        run_id = run_data.get('run', {}).get('id')
        run_name = run_data.get('run', {}).get('name')
        
        print(f"✅ Pipeline run submitted successfully!")
        print(f"Run ID: {run_id}")
        print(f"Run Name: {run_name}")
        return run_id, run_name
        
    except Exception as e:
        print(f"Error submitting pipeline run: {e}")
        if hasattr(e, 'response'):
            print(f"Response: {e.response.text}")
        return None, None

def monitor_pipeline_run(dspa_host, token, run_id, namespace="petloan-instructlab"):
    """Monitor pipeline run progress"""
    url = f"https://{dspa_host}/apis/v1beta1/runs/{run_id}"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    print("\n🔍 Monitoring pipeline progress...")
    last_status = None
    
    while True:
        try:
            response = requests.get(url, headers=headers, verify=False)
            response.raise_for_status()
            data = response.json()
            
            run_detail = data.get('run', {})
            status = run_detail.get('status', 'Unknown')
            
            # Check workflow status
            pipeline_runtime = run_detail.get('pipeline_runtime', {})
            workflow_manifest = pipeline_runtime.get('workflow_manifest')
            
            if workflow_manifest:
                try:
                    workflow_data = json.loads(workflow_manifest)
                    workflow_status = workflow_data.get('status', {})
                    nodes = workflow_status.get('nodes', {})
                    
                    total_nodes = len(nodes)
                    completed_nodes = sum(1 for node in nodes.values() 
                                        if node.get('phase') in ['Succeeded', 'Failed', 'Error'])
                    
                    progress_pct = int((completed_nodes / total_nodes) * 100) if total_nodes > 0 else 0
                    
                    if status != last_status:
                        print(f"\n📊 Pipeline Status: {status}")
                        print(f"🔄 Progress: {completed_nodes}/{total_nodes} steps ({progress_pct}%)")
                        
                        # Check for any failed nodes
                        failed_nodes = [name for name, node in nodes.items() 
                                      if node.get('phase') == 'Failed']
                        if failed_nodes:
                            print(f"❌ Failed steps: {', '.join(failed_nodes[:3])}")
                        
                        last_status = status
                    
                    # Check if completed
                    if status in ['Succeeded', 'Failed', 'Error']:
                        print(f"\n🏁 Pipeline completed with status: {status}")
                        if status == 'Succeeded':
                            print("✅ Pipeline completed successfully!")
                        else:
                            print(f"❌ Pipeline failed with status: {status}")
                        break
                        
                except json.JSONDecodeError:
                    print("Warning: Could not parse workflow manifest")
            
            time.sleep(30)  # Check every 30 seconds
            
        except KeyboardInterrupt:
            print("\n⏸️  Monitoring interrupted by user")
            break
        except Exception as e:
            print(f"Error monitoring pipeline: {e}")
            time.sleep(60)

def main():
    parser = argparse.ArgumentParser(description='Submit and monitor InstructLab pipeline with NFS storage')
    parser.add_argument('--route', type=str, help='DSPA route (auto-detected if not provided)')
    parser.add_argument('--namespace', type=str, default='petloan-instructlab', help='Namespace')
    parser.add_argument('--monitor', action='store_true', help='Monitor the pipeline after submission')
    
    args = parser.parse_args()
    
    print("🚀 Starting InstructLab Pipeline with NFS Storage...")
    
    # Get authentication token
    print("🔑 Getting authentication token...")
    token = get_bearer_token()
    
    # Get DSPA route
    if args.route:
        dspa_host = args.route
        print(f"📍 Using provided route: {dspa_host}")
    else:
        print("🔍 Auto-detecting DSPA route...")
        dspa_host = get_dspa_route(args.namespace)
        print(f"📍 Found DSPA route: {dspa_host}")
    
    # Get pipeline information
    print("📋 Getting pipeline information...")
    pipeline_id = get_pipeline_info(dspa_host, token, args.namespace)
    
    if not pipeline_id:
        print("❌ Could not find pipeline")
        sys.exit(1)
    
    # Submit pipeline run
    print("📤 Submitting pipeline run with NFS storage...")
    run_id, run_name = submit_pipeline_run(dspa_host, token, pipeline_id, args.namespace)
    
    if not run_id:
        print("❌ Failed to submit pipeline run")
        sys.exit(1)
    
    # Monitor if requested
    if args.monitor:
        monitor_pipeline_run(dspa_host, token, run_id, args.namespace)
    else:
        print(f"\n✅ Pipeline submitted! Run ID: {run_id}")
        print(f"To monitor: python3 {sys.argv[0]} --monitor --route {dspa_host}")

if __name__ == "__main__":
    main()
