#!/usr/bin/env python3

import argparse
import json
import time
import requests
import subprocess
import sys
from urllib3.exceptions import InsecureRequestWarning
from datetime import datetime

# Suppress SSL warnings
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def get_bearer_token():
    """Extract bearer token from oc command"""
    try:
        result = subprocess.run(['oc', 'whoami', '--show-token'], 
                              capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Error getting token: {e}")
        sys.exit(1)

def get_dspa_route(namespace="petloan-instructlab"):
    """Get the Data Science Pipeline Application route"""
    try:
        result = subprocess.run(['oc', 'get', 'route', 'ds-pipeline-dspa', 
                               '-n', namespace, '-o', 'jsonpath={.spec.host}'], 
                              capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Error getting route: {e}")
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
                    print(f"✅ Found InstructLab pipeline: {pipeline['display_name']}")
                    return pipeline['id']
            
            # If no InstructLab pipeline found, use the first one
            pipeline = data['pipelines'][0]
            print(f"✅ Using pipeline: {pipeline['display_name']}")
            return pipeline['id']
        else:
            print("❌ No pipelines found")
            return None
    except Exception as e:
        print(f"❌ Error getting pipeline info: {e}")
        return None

def submit_pipeline_run(dspa_host, token, pipeline_id, namespace="petloan-instructlab"):
    """Submit production pipeline run with optimized parameters"""
    
    url = f"https://{dspa_host}/apis/v1beta1/runs"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Production-optimized parameters based on successful dpltw run
    timestamp = int(time.time())
    pipeline_spec = {
        "display_name": f"InstructLab-Production-{timestamp}",
        "description": "Production InstructLab pipeline run with proven stable configuration",
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
                {"name": "storage_class_name", "value": "gp3"},  # Use proven working storage
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
        
        print(f"🚀 Pipeline run submitted successfully!")
        print(f"📝 Run ID: {run_id}")
        print(f"📝 Run Name: {run_name}")
        print(f"🕒 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return run_id, run_name
        
    except Exception as e:
        print(f"❌ Error submitting pipeline run: {e}")
        if hasattr(e, 'response'):
            print(f"Response: {e.response.text}")
        return None, None

def monitor_pipeline_run(dspa_host, token, run_id, namespace="petloan-instructlab"):
    """Monitor pipeline run progress with detailed status reporting"""
    url = f"https://{dspa_host}/apis/v1beta1/runs/{run_id}"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    print("\n🔍 Starting continuous monitoring...")
    print("📊 Will check progress every 10 minutes for 24 hours")
    print("⚠️  Monitoring will stop immediately if pipeline fails")
    
    last_status = None
    last_progress = -1
    start_time = time.time()
    max_duration = 24 * 60 * 60  # 24 hours in seconds
    check_interval = 10 * 60  # 10 minutes in seconds
    
    while time.time() - start_time < max_duration:
        try:
            response = requests.get(url, headers=headers, verify=False)
            response.raise_for_status()
            data = response.json()
            
            run_detail = data.get('run', {})
            status = run_detail.get('status', 'Unknown')
            
            # Check workflow status
            pipeline_runtime = run_detail.get('pipeline_runtime', {})
            workflow_manifest = pipeline_runtime.get('workflow_manifest')
            
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            elapsed_hours = (time.time() - start_time) / 3600
            
            if workflow_manifest:
                try:
                    workflow_data = json.loads(workflow_manifest)
                    workflow_status = workflow_data.get('status', {})
                    nodes = workflow_status.get('nodes', {})
                    
                    total_nodes = len(nodes)
                    completed_nodes = sum(1 for node in nodes.values() 
                                        if node.get('phase') in ['Succeeded', 'Failed', 'Error'])
                    running_nodes = sum(1 for node in nodes.values() 
                                      if node.get('phase') == 'Running')
                    failed_nodes = [name for name, node in nodes.items() 
                                  if node.get('phase') == 'Failed']
                    
                    progress_pct = int((completed_nodes / total_nodes) * 100) if total_nodes > 0 else 0
                    
                    if status != last_status or progress_pct != last_progress:
                        print(f"\n⏰ [{current_time}] Status Update (Elapsed: {elapsed_hours:.1f}h)")
                        print(f"📊 Pipeline Status: {status}")
                        print(f"🔄 Progress: {completed_nodes}/{total_nodes} steps ({progress_pct}%)")
                        if running_nodes > 0:
                            print(f"🏃 Running steps: {running_nodes}")
                        
                        if failed_nodes:
                            print(f"❌ FAILED STEPS DETECTED: {', '.join(failed_nodes[:3])}")
                            print("🛑 STOPPING MONITORING DUE TO FAILURES")
                            return False
                        
                        last_status = status
                        last_progress = progress_pct
                    
                    # Check if completed
                    if status in ['Succeeded', 'Failed', 'Error']:
                        print(f"\n🏁 Pipeline completed with status: {status}")
                        if status == 'Succeeded':
                            print("✅ PIPELINE COMPLETED SUCCESSFULLY!")
                            print(f"🕒 Total Duration: {elapsed_hours:.1f} hours")
                            return True
                        else:
                            print(f"❌ PIPELINE FAILED with status: {status}")
                            return False
                        
                except json.JSONDecodeError:
                    print("⚠️  Warning: Could not parse workflow manifest")
            
            # Wait for next check
            next_check_time = datetime.fromtimestamp(time.time() + check_interval)
            print(f"💤 Sleeping for 10 minutes... (Next check: {next_check_time.strftime('%H:%M:%S')})")
            time.sleep(check_interval)
            
        except KeyboardInterrupt:
            print("\n⏸️  Monitoring interrupted by user")
            break
        except Exception as e:
            print(f"❌ Error monitoring pipeline: {e}")
            print("🔄 Retrying in 10 minutes...")
            time.sleep(check_interval)
    
    print(f"\n⏰ 24-hour monitoring period completed")
    return None

def main():
    parser = argparse.ArgumentParser(description='Submit and monitor InstructLab production pipeline')
    parser.add_argument('--route', type=str, help='DSPA route (auto-detected if not provided)')
    parser.add_argument('--namespace', type=str, default='petloan-instructlab', help='Namespace')
    parser.add_argument('--no-monitor', action='store_true', help='Submit only, do not monitor')
    
    args = parser.parse_args()
    
    print("🚀 Starting InstructLab Production Pipeline...")
    print("🎯 Configuration: Optimized for proven stability")
    
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
    print("📤 Submitting production pipeline run...")
    run_id, run_name = submit_pipeline_run(dspa_host, token, pipeline_id, args.namespace)
    
    if not run_id:
        print("❌ Failed to submit pipeline run")
        sys.exit(1)
    
    # Monitor if requested
    if not args.no_monitor:
        success = monitor_pipeline_run(dspa_host, token, run_id, args.namespace)
        if success is True:
            print("\n🎉 MISSION ACCOMPLISHED!")
            sys.exit(0)
        elif success is False:
            print("\n💥 PIPELINE FAILED")
            sys.exit(1)
        else:
            print("\n⏰ MONITORING TIMEOUT")
            sys.exit(2)
    else:
        print(f"\n✅ Pipeline submitted! Run ID: {run_id}")
        print(f"To monitor: python3 {sys.argv[0]} --route {dspa_host}")

if __name__ == "__main__":
    main()
