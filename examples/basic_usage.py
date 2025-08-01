#!/usr/bin/env python3
"""
Basic usage example for Prime Compute Manager.

This example demonstrates how to:
1. Find available GPU resources
2. Create a compute pod
3. Monitor pod status
4. Terminate the pod when done
"""

import asyncio
import time
from prime_compute_manager import PrimeManager


def main():
    """Basic usage example."""
    print("🚀 Prime Compute Manager - Basic Usage Example")
    print("=" * 50)

    # Initialize manager
    manager = PrimeManager()

    # 1. Find available GPU resources
    print("\n1. Finding available GPU resources...")
    try:
        resources = manager.find_gpus(
            gpu_type="H100_80GB", min_count=2, max_cost_per_hour=5.0
        )

        print(f"Found {len(resources)} resource options:")
        for resource in resources:
            print(
                f"  - {resource.provider}: {resource.available_count}/{resource.total_count} "
                f"{resource.gpu_type.value} GPUs at ${resource.cost_per_hour:.2f}/hour "
                f"in {resource.region}"
            )

        if not resources:
            print("❌ No suitable resources found")
            return

    except Exception as e:
        print(f"❌ Error finding resources: {e}")
        return

    # 2. Create a compute pod
    print("\n2. Creating compute pod...")
    try:
        pod = manager.create_pod(
            gpu_type="H100_80GB",
            gpu_count=2,
            name="example-training-pod",
            region="us-west-2",
        )

        print(f"✅ Pod created successfully!")
        print(f"   ID: {pod.id}")
        print(f"   Name: {pod.name}")
        print(f"   Status: {pod.status.value}")
        print(f"   GPUs: {pod.gpu_count}x {pod.gpu_type.value}")
        print(f"   Cost: ${pod.cost_per_hour:.2f}/hour")

    except Exception as e:
        print(f"❌ Error creating pod: {e}")
        return

    # 3. Monitor pod status
    print("\n3. Monitoring pod status...")
    for i in range(3):
        try:
            updated_pod = manager.get_pod_status(pod.id)
            print(f"   Check {i + 1}: Status = {updated_pod.status.value}")

            if updated_pod.status.value == "running":
                print(f"   🎉 Pod is running! SSH: {updated_pod.ssh_connection}")
                break

            time.sleep(2)

        except Exception as e:
            print(f"❌ Error checking status: {e}")
            break

    # 4. List all pods
    print("\n4. Listing all active pods...")
    try:
        all_pods = manager.list_pods()
        print(f"   Found {len(all_pods)} active pods:")

        for p in all_pods:
            runtime = p.runtime_hours
            cost = p.total_cost
            print(
                f"   - {p.name} ({p.id[:12]}...): {p.status.value}, "
                f"runtime: {runtime:.1f}h, cost: ${cost:.2f}"
            )

    except Exception as e:
        print(f"❌ Error listing pods: {e}")

    # 5. Terminate pod
    print("\n5. Terminating pod...")
    try:
        success = manager.terminate_pod(pod.id)
        if success:
            print(f"✅ Pod {pod.name} terminated successfully")

            # Check final status
            final_pod = manager.get_pod_status(pod.id)
            print(f"   Final status: {final_pod.status.value}")
            print(f"   Total runtime: {final_pod.runtime_hours:.1f} hours")
            print(f"   Total cost: ${final_pod.total_cost:.2f}")
        else:
            print(f"❌ Failed to terminate pod")

    except Exception as e:
        print(f"❌ Error terminating pod: {e}")

    print("\n🎯 Example completed!")


if __name__ == "__main__":
    main()
