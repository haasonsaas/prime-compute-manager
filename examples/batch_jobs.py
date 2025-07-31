#!/usr/bin/env python3
"""
Batch job processing example for Prime Compute Manager.

This example demonstrates how to:
1. Set up a job queue
2. Add multiple jobs
3. Process jobs in parallel
4. Monitor job progress
"""

import asyncio
from prime_compute_manager import PrimeManager, JobQueue


async def main():
    """Batch job processing example."""
    print("🚀 Prime Compute Manager - Batch Job Processing Example")
    print("=" * 60)
    
    # Initialize manager and job queue
    manager = PrimeManager()
    queue = JobQueue(manager, max_concurrent_jobs=3)
    
    # 1. Add multiple jobs to the queue
    print("\n1. Adding jobs to queue...")
    
    jobs = [
        {
            "name": "data-preprocessing",
            "script": "preprocess_data.py",
            "args": {"input_dir": "/data/raw", "output_dir": "/data/processed"},
            "gpu_type": "H100_80GB",
            "gpu_count": 1
        },
        {
            "name": "model-training-1",
            "script": "train_model.py", 
            "args": {"config": "config_1.yaml", "epochs": 100},
            "gpu_type": "H100_80GB",
            "gpu_count": 2
        },
        {
            "name": "model-training-2",
            "script": "train_model.py",
            "args": {"config": "config_2.yaml", "epochs": 100},
            "gpu_type": "H100_80GB", 
            "gpu_count": 2
        },
        {
            "name": "hyperparameter-search",
            "script": "hyperparam_search.py",
            "args": {"search_space": "large", "trials": 50},
            "gpu_type": "H100_80GB",
            "gpu_count": 4
        },
        {
            "name": "model-evaluation",
            "script": "evaluate_models.py",
            "args": {"model_dir": "/models", "test_data": "/data/test"},
            "gpu_type": "H100_80GB",
            "gpu_count": 1
        }
    ]
    
    created_jobs = []
    for job_config in jobs:
        job = queue.add_job(
            name=str(job_config["name"]),
            script_path=str(job_config["script"]),
            args=job_config["args"],  # type: ignore
            gpu_type=str(job_config["gpu_type"]),
            gpu_count=job_config["gpu_count"]  # type: ignore
        )
        created_jobs.append(job)
        print(f"   ✅ Added job: {job.name} ({job.id[:12]}...)")
    
    print(f"\n   Total jobs added: {len(created_jobs)}")
    
    # 2. Start processing jobs
    print("\n2. Starting job processing...")
    print("   Processing jobs with max 3 concurrent executions...")
    
    # Create a task for monitoring progress
    async def monitor_progress():
        """Monitor job progress while processing."""
        while True:
            jobs = queue.list_jobs()
            
            pending = len([j for j in jobs if j.status.value == "pending"])
            running = len([j for j in jobs if j.status.value == "running"])
            completed = len([j for j in jobs if j.status.value == "completed"])
            failed = len([j for j in jobs if j.status.value == "failed"])
            
            print(f"   📊 Status: {pending} pending, {running} running, "
                  f"{completed} completed, {failed} failed")
            
            # Show running jobs
            running_jobs = [j for j in jobs if j.status.value == "running"]
            for job in running_jobs:
                runtime = (job.started_at and 
                          (asyncio.get_event_loop().time() - job.started_at.timestamp()) / 60) or 0
                print(f"      🏃 {job.name}: running for {runtime:.1f} minutes")
            
            # Check if all done
            if pending == 0 and running == 0:
                break
                
            await asyncio.sleep(10)
    
    # Run processing and monitoring concurrently
    processing_task = asyncio.create_task(queue.process_all())
    monitoring_task = asyncio.create_task(monitor_progress())
    
    await processing_task
    monitoring_task.cancel()
    
    print("\n3. Job processing completed!")
    
    # 4. Show final results
    print("\n4. Final results:")
    final_jobs = queue.list_jobs()
    
    for job in final_jobs:
        status_icon = {
            "completed": "✅",
            "failed": "❌", 
            "cancelled": "⚠️"
        }.get(job.status.value, "❓")
        
        runtime = job.runtime_seconds / 60 if job.runtime_seconds else 0
        
        print(f"   {status_icon} {job.name}")
        print(f"      Status: {job.status.value}")
        print(f"      Runtime: {runtime:.1f} minutes")
        
        if job.pod_id:
            try:
                pod = manager.get_pod_status(job.pod_id)
                print(f"      Cost: ${pod.total_cost:.2f}")
            except:
                pass
        
        if job.error_message:
            print(f"      Error: {job.error_message}")
        elif job.output_path:
            print(f"      Output: {job.output_path}")
        
        print()
    
    # 5. Calculate total costs
    print("5. Cost summary:")
    total_cost = 0.0
    total_runtime = 0.0
    
    for job in final_jobs:
        if job.pod_id:
            try:
                pod = manager.get_pod_status(job.pod_id)
                total_cost += pod.total_cost
                total_runtime += pod.runtime_hours
            except:
                pass
    
    print(f"   Total runtime: {total_runtime:.1f} hours")
    print(f"   Total cost: ${total_cost:.2f}")
    print(f"   Average cost per job: ${total_cost / len(final_jobs):.2f}")
    
    # 6. Success/failure summary
    completed = len([j for j in final_jobs if j.status.value == "completed"])
    failed = len([j for j in final_jobs if j.status.value == "failed"])
    
    print(f"\n6. Summary:")
    print(f"   ✅ Completed: {completed}/{len(final_jobs)} jobs")
    print(f"   ❌ Failed: {failed}/{len(final_jobs)} jobs")
    print(f"   📊 Success rate: {completed/len(final_jobs)*100:.1f}%")
    
    print("\n🎯 Batch processing example completed!")


if __name__ == "__main__":
    asyncio.run(main())