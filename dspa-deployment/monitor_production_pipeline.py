#!/usr/bin/env python3

import json
import time
import subprocess
import sys
from datetime import datetime, timedelta

def run_kubectl(cmd):
    """Run kubectl command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running command: {cmd}")
        print(f"Error: {e.stderr}")
        return None

def get_workflow_status(workflow_name):
    """Get detailed workflow status"""
    cmd = f"kubectl get workflow {workflow_name} -n petloan-instructlab -o json"
    output = run_kubectl(cmd)
    
    if output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return None
    return None

def get_workflow_pods(workflow_name):
    """Get pods associated with the workflow"""
    cmd = f"kubectl get pods -n petloan-instructlab --selector=workflows.argoproj.io/workflow={workflow_name} -o json"
    output = run_kubectl(cmd)
    
    if output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return None
    return None

def analyze_workflow_progress(workflow_data):
    """Analyze workflow progress and return detailed status"""
    if not workflow_data:
        return None
    
    status = workflow_data.get('status', {})
    
    # Basic workflow info
    workflow_status = status.get('phase', 'Unknown')
    start_time = workflow_data.get('metadata', {}).get('creationTimestamp')
    finish_time = status.get('finishedAt')
    
    # Node analysis
    nodes = status.get('nodes', {})
    total_nodes = len(nodes)
    
    completed_nodes = []
    running_nodes = []
    failed_nodes = []
    pending_nodes = []
    
    for name, node in nodes.items():
        phase = node.get('phase', 'Unknown')
        if phase == 'Succeeded':
            completed_nodes.append(name)
        elif phase == 'Running':
            running_nodes.append(name)
        elif phase in ['Failed', 'Error']:
            failed_nodes.append(name)
        elif phase in ['Pending']:
            pending_nodes.append(name)
    
    progress_pct = int((len(completed_nodes) / total_nodes) * 100) if total_nodes > 0 else 0
    
    return {
        'workflow_status': workflow_status,
        'start_time': start_time,
        'finish_time': finish_time,
        'total_nodes': total_nodes,
        'completed_nodes': len(completed_nodes),
        'running_nodes': len(running_nodes),
        'failed_nodes': len(failed_nodes),
        'pending_nodes': len(pending_nodes),
        'progress_pct': progress_pct,
        'failed_node_names': failed_nodes,
        'running_node_names': running_nodes,
        'completed_node_names': completed_nodes
    }

def format_duration(start_time_str):
    """Calculate and format duration since start time"""
    try:
        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        now = datetime.now(start_time.tzinfo)
        duration = now - start_time
        
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        
        return f"{hours}h {minutes}m"
    except:
        return "Unknown"

def print_status_update(workflow_name, progress_info, iteration):
    """Print formatted status update"""
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"\n{'='*80}")
    print(f"🔍 PIPELINE MONITORING UPDATE #{iteration}")
    print(f"⏰ Time: {current_time}")
    print(f"📊 Workflow: {workflow_name}")
    print(f"{'='*80}")
    
    if not progress_info:
        print("❌ Unable to retrieve workflow status")
        return
    
    # Duration calculation
    duration = format_duration(progress_info['start_time']) if progress_info['start_time'] else "Unknown"
    
    print(f"📈 Status: {progress_info['workflow_status']}")
    print(f"⏱️  Duration: {duration}")
    print(f"🔄 Progress: {progress_info['completed_nodes']}/{progress_info['total_nodes']} steps ({progress_info['progress_pct']}%)")
    
    if progress_info['running_nodes'] > 0:
        print(f"🏃 Running: {progress_info['running_nodes']} steps")
        print(f"   Current tasks: {', '.join(progress_info['running_node_names'][:3])}")
    
    if progress_info['pending_nodes'] > 0:
        print(f"⏳ Pending: {progress_info['pending_nodes']} steps")
    
    if progress_info['failed_nodes'] > 0:
        print(f"❌ Failed: {progress_info['failed_nodes']} steps")
        print(f"   Failed tasks: {', '.join(progress_info['failed_node_names'][:3])}")
        return False  # Signal failure
    
    # Progress bar
    bar_length = 50
    filled_length = int(bar_length * progress_info['progress_pct'] // 100)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    print(f"📊 [{bar}] {progress_info['progress_pct']}%")
    
    return True

def monitor_pipeline():
    """Main monitoring function"""
    workflow_name = "instructlab-production-z4fqp"
    
    print("🚀 STARTING INSTRUCTLAB PRODUCTION PIPELINE MONITORING")
    print("=" * 80)
    print(f"📊 Workflow: {workflow_name}")
    print(f"⏰ Monitoring Duration: 24 hours")
    print(f"🔄 Check Interval: 10 minutes")
    print(f"🛑 Will stop immediately on failures")
    print("=" * 80)
    
    start_time = time.time()
    max_duration = 24 * 60 * 60  # 24 hours in seconds
    check_interval = 10 * 60  # 10 minutes in seconds
    
    last_progress = -1
    iteration = 1
    
    while time.time() - start_time < max_duration:
        try:
            # Get workflow status
            workflow_data = get_workflow_status(workflow_name)
            progress_info = analyze_workflow_progress(workflow_data)
            
            # Print status only if there's a change or every 6 checks (1 hour)
            should_print = (
                not progress_info or 
                progress_info['progress_pct'] != last_progress or 
                iteration % 6 == 1 or
                progress_info['failed_nodes'] > 0 or
                progress_info['workflow_status'] in ['Succeeded', 'Failed', 'Error']
            )
            
            if should_print:
                success = print_status_update(workflow_name, progress_info, iteration)
                
                if not success:
                    print("\n💥 PIPELINE FAILED - STOPPING MONITORING")
                    return False
                
                if progress_info and progress_info['workflow_status'] in ['Succeeded', 'Failed', 'Error']:
                    if progress_info['workflow_status'] == 'Succeeded':
                        print("\n🎉 PIPELINE COMPLETED SUCCESSFULLY!")
                        return True
                    else:
                        print(f"\n💥 PIPELINE FAILED WITH STATUS: {progress_info['workflow_status']}")
                        return False
                
                if progress_info:
                    last_progress = progress_info['progress_pct']
            
            # Sleep until next check
            next_check = datetime.now() + timedelta(seconds=check_interval)
            if iteration == 1 or should_print:
                print(f"💤 Next check at: {next_check.strftime('%H:%M:%S')}")
            
            time.sleep(check_interval)
            iteration += 1
            
        except KeyboardInterrupt:
            print("\n⏸️  Monitoring interrupted by user")
            return None
        except Exception as e:
            print(f"\n❌ Error during monitoring: {e}")
            print("🔄 Retrying in 10 minutes...")
            time.sleep(check_interval)
            iteration += 1
    
    print(f"\n⏰ 24-hour monitoring period completed")
    return None

if __name__ == "__main__":
    result = monitor_pipeline()
    
    if result is True:
        print("\n🎉 MISSION ACCOMPLISHED!")
        sys.exit(0)
    elif result is False:
        print("\n💥 PIPELINE FAILED")
        sys.exit(1)
    else:
        print("\n⏰ MONITORING TIMEOUT OR INTERRUPTED")
        sys.exit(2)
