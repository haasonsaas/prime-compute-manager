#!/usr/bin/env python3
"""
Resource monitoring example for Prime Compute Manager.

This example demonstrates how to:
1. Set up resource monitoring
2. Configure alerts
3. Monitor team usage
4. Track costs and utilization
"""

import time
from prime_compute_manager import PrimeManager, ResourceMonitor


def main():
    """Resource monitoring example."""
    print("🚀 Prime Compute Manager - Resource Monitoring Example")
    print("=" * 60)
    
    # Initialize manager and monitor
    manager = PrimeManager()
    monitor = ResourceMonitor(manager, check_interval=30)  # Check every 30 seconds
    
    # 1. Create some pods to monitor
    print("\n1. Creating test pods for monitoring...")
    test_pods = []
    
    for i in range(3):
        try:
            pod = manager.create_pod(
                gpu_type="H100_80GB",
                gpu_count=2,
                name=f"monitoring-test-pod-{i+1}"
            )
            test_pods.append(pod)
            print(f"   ✅ Created pod: {pod.name}")
        except Exception as e:
            print(f"   ❌ Error creating pod {i+1}: {e}")
    
    # 2. Set up monitoring alerts
    print("\n2. Setting up monitoring alerts...")
    
    alerts = [
        {
            "name": "High Cost Alert",
            "condition": "cost_per_hour > 10",
            "action": "email",
            "recipient": "admin@company.com"
        },
        {
            "name": "Too Many Active Pods",
            "condition": "active_pods > 5",
            "action": "webhook", 
            "recipient": "https://hooks.slack.com/services/xxx"
        },
        {
            "name": "GPU Limit Warning",
            "condition": "total_gpus > 8",
            "action": "email",
            "recipient": "team@company.com"
        }
    ]
    
    for alert_config in alerts:
        alert = monitor.add_alert(
            name=alert_config["name"],
            condition=alert_config["condition"],
            action=alert_config["action"],
            recipient=alert_config["recipient"]
        )
        print(f"   ✅ Added alert: {alert.name}")
    
    # 3. Start monitoring
    print("\n3. Starting resource monitoring...")
    monitor.start()
    print("   📊 Monitor started (checking every 30 seconds)")
    
    # 4. Monitor for a while and show updates
    print("\n4. Monitoring resource usage...")
    
    for minute in range(1, 6):  # Monitor for 5 minutes
        print(f"\n   --- Minute {minute} ---")
        
        try:
            # Get current usage
            usage = monitor.get_team_usage()
            
            print(f"   Active pods: {usage.active_pods}")
            print(f"   Total GPUs used: {usage.total_gpus_used}")
            print(f"   Current cost/hour: ${usage.current_cost_per_hour:.2f}")
            print(f"   Total cost today: ${usage.total_cost_today:.2f}")
            
            # Show pod breakdown
            if usage.pod_breakdown:
                print("   Pod breakdown:")
                for pod in usage.pod_breakdown:
                    runtime = pod.runtime_hours
                    print(f"     - {pod.name}: {pod.gpu_count} GPUs, "
                          f"{runtime:.1f}h runtime, ${pod.total_cost:.2f} cost")
            
            # Check if any alerts were triggered
            alerts_list = monitor.list_alerts()
            triggered = [a for a in alerts_list if a.last_triggered]
            if triggered:
                print(f"   🚨 {len(triggered)} alert(s) triggered!")
                for alert in triggered:
                    print(f"     - {alert.name}: {alert.condition}")
            
        except Exception as e:
            print(f"   ❌ Error getting usage: {e}")
        
        # Wait before next check
        if minute < 5:
            print("   ⏳ Waiting 60 seconds...")
            time.sleep(60)
    
    # 5. Demonstrate alert conditions
    print("\n5. Testing alert conditions...")
    
    # Create more pods to trigger alerts
    additional_pods = []
    for i in range(3):
        try:
            pod = manager.create_pod(
                gpu_type="H100_80GB",
                gpu_count=4,  # More GPUs to trigger alerts
                name=f"alert-test-pod-{i+1}"
            )
            additional_pods.append(pod)
            print(f"   ✅ Created high-GPU pod: {pod.name}")
        except Exception as e:
            print(f"   ❌ Error creating alert test pod {i+1}: {e}")
    
    # Check usage after creating more pods
    print("\n   Checking usage after creating more pods...")
    try:
        usage = monitor.get_team_usage()
        print(f"   Active pods: {usage.active_pods}")
        print(f"   Total GPUs used: {usage.total_gpus_used}")
        print(f"   Current cost/hour: ${usage.current_cost_per_hour:.2f}")
        
        # Wait for alerts to trigger
        print("   ⏳ Waiting for alerts to check conditions...")
        time.sleep(35)  # Wait longer than check interval
        
        # Check for triggered alerts
        alerts_list = monitor.list_alerts()
        for alert in alerts_list:
            if alert.last_triggered:
                print(f"   🚨 Alert triggered: {alert.name}")
                print(f"      Condition: {alert.condition}")
                print(f"      Action: {alert.action} to {alert.recipient}")
        
    except Exception as e:
        print(f"   ❌ Error testing alerts: {e}")
    
    # 6. Show usage history
    print("\n6. Usage history:")
    try:
        history = monitor.get_usage_history(hours=1)
        print(f"   Found {len(history)} usage snapshots in the last hour")
        
        if history:
            latest = history[-1]
            earliest = history[0] if len(history) > 1 else latest
            
            print("   Trend analysis:")
            print(f"     Cost/hour: ${earliest.current_cost_per_hour:.2f} → "
                  f"${latest.current_cost_per_hour:.2f}")
            print(f"     Active pods: {earliest.active_pods} → {latest.active_pods}")
            print(f"     GPU usage: {earliest.total_gpus_used} → {latest.total_gpus_used}")
    
    except Exception as e:
        print(f"   ❌ Error getting history: {e}")
    
    # 7. Clean up
    print("\n7. Cleaning up...")
    
    # Stop monitoring
    monitor.stop()
    print("   ✅ Monitoring stopped")
    
    # Terminate test pods
    all_test_pods = test_pods + additional_pods
    for pod in all_test_pods:
        try:
            success = manager.terminate_pod(pod.id)
            if success:
                print(f"   ✅ Terminated pod: {pod.name}")
            else:
                print(f"   ❌ Failed to terminate pod: {pod.name}")
        except Exception as e:
            print(f"   ❌ Error terminating pod {pod.name}: {e}")
    
    # Final cost summary
    print("\n8. Final cost summary:")
    total_cost = 0.0
    for pod in all_test_pods:
        try:
            final_pod = manager.get_pod_status(pod.id)
            total_cost += final_pod.total_cost
            print(f"   {final_pod.name}: ${final_pod.total_cost:.2f} "
                  f"({final_pod.runtime_hours:.1f} hours)")
        except Exception as e:
            print(f"   Error getting final cost for {pod.name}: {e}")
    
    print(f"\n   Total monitoring demo cost: ${total_cost:.2f}")
    print("\n🎯 Resource monitoring example completed!")


if __name__ == "__main__":
    main()