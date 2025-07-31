"""Resource monitoring and alerting."""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from .manager import PrimeManager
from .models import TeamUsage, Alert, Pod


class ResourceMonitor:
    """Monitors resource usage and sends alerts."""
    
    def __init__(self, manager: PrimeManager, check_interval: int = 60):
        """Initialize resource monitor.
        
        Args:
            manager: PrimeManager instance
            check_interval: Check interval in seconds
        """
        self.manager = manager
        self.check_interval = check_interval
        self._alerts: Dict[str, Alert] = {}
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._usage_history: List[TeamUsage] = []
    
    def add_alert(
        self,
        name: str,
        condition: str,
        action: str,
        recipient: str,
        **kwargs
    ) -> Alert:
        """Add a resource usage alert.
        
        Args:
            name: Alert name
            condition: Alert condition (e.g., "cost_per_hour > 50")
            action: Action to take (e.g., "email", "webhook")
            recipient: Alert recipient
            **kwargs: Additional alert configuration
            
        Returns:
            Created alert
        """
        alert = Alert(
            id=f"alert-{len(self._alerts)}",
            name=name,
            condition=condition,
            action=action,
            recipient=recipient
        )
        
        self._alerts[alert.id] = alert
        return alert
    
    def remove_alert(self, alert_id: str) -> bool:
        """Remove an alert.
        
        Args:
            alert_id: Alert identifier
            
        Returns:
            True if successful
        """
        if alert_id in self._alerts:
            del self._alerts[alert_id]
            return True
        return False
    
    def get_team_usage(self, team_name: Optional[str] = None) -> TeamUsage:
        """Get current team resource usage.
        
        Args:
            team_name: Optional team name
            
        Returns:
            Team usage information
        """
        try:
            # Get all active pods
            pods = self.manager.list_pods(active_only=True)
            
            active_pods = len(pods)
            total_gpus_used = sum(pod.gpu_count for pod in pods)
            current_cost_per_hour = sum(pod.cost_per_hour for pod in pods)
            
            # Calculate today's cost
            total_cost_today = 0.0
            for pod in pods:
                if pod.started_at and pod.started_at.date() == datetime.utcnow().date():
                    total_cost_today += pod.total_cost
            
            # Calculate month's cost (simplified)
            total_cost_month = total_cost_today * 30  # Rough estimate
            
            usage = TeamUsage(
                team_name=team_name or "default",
                active_pods=active_pods,
                total_gpus_used=total_gpus_used,
                current_cost_per_hour=current_cost_per_hour,
                total_cost_today=total_cost_today,
                total_cost_month=total_cost_month,
                pod_breakdown=pods
            )
            
            # Store in history
            self._usage_history.append(usage)
            
            # Keep only last 24 hours of history
            cutoff = datetime.utcnow() - timedelta(hours=24)
            self._usage_history = [
                u for u in self._usage_history 
                if hasattr(u, 'timestamp') and u.timestamp > cutoff
            ]
            
            return usage
            
        except Exception as e:
            raise RuntimeError(f"Failed to get team usage: {e}")
    
    def _check_alerts(self, usage: TeamUsage) -> None:
        """Check all alerts against current usage.
        
        Args:
            usage: Current team usage
        """
        for alert in self._alerts.values():
            if not alert.is_active:
                continue
            
            try:
                # Simple condition evaluation
                # In production, would use a proper expression evaluator
                condition = alert.condition.replace("cost_per_hour", str(usage.current_cost_per_hour))
                condition = condition.replace("active_pods", str(usage.active_pods))
                condition = condition.replace("total_gpus", str(usage.total_gpus_used))
                
                if eval(condition):  # Note: eval is unsafe, use proper parser in production
                    self._trigger_alert(alert, usage)
                    
            except Exception as e:
                print(f"Error evaluating alert {alert.name}: {e}")
    
    def _trigger_alert(self, alert: Alert, usage: TeamUsage) -> None:
        """Trigger an alert.
        
        Args:
            alert: Alert to trigger
            usage: Current usage that triggered the alert
        """
        # Prevent spam - only trigger once per hour
        if (alert.last_triggered and 
            datetime.utcnow() - alert.last_triggered < timedelta(hours=1)):
            return
        
        alert.last_triggered = datetime.utcnow()
        
        message = (
            f"Alert: {alert.name}\n"
            f"Condition: {alert.condition}\n"
            f"Current usage:\n"
            f"  - Active pods: {usage.active_pods}\n"
            f"  - Total GPUs: {usage.total_gpus_used}\n"
            f"  - Cost per hour: ${usage.current_cost_per_hour:.2f}\n"
            f"  - Total cost today: ${usage.total_cost_today:.2f}"
        )
        
        if alert.action == "email":
            self._send_email_alert(alert.recipient, alert.name, message)
        elif alert.action == "webhook":
            self._send_webhook_alert(alert.recipient, alert.name, message)
        else:
            print(f"Alert triggered: {message}")
    
    def _send_email_alert(self, recipient: str, subject: str, message: str) -> None:
        """Send email alert (mock implementation).
        
        Args:
            recipient: Email recipient
            subject: Email subject
            message: Email message
        """
        # Mock implementation - in real code, would use email service
        print(f"EMAIL ALERT to {recipient}: {subject}\n{message}")
    
    def _send_webhook_alert(self, webhook_url: str, subject: str, message: str) -> None:
        """Send webhook alert (mock implementation).
        
        Args:
            webhook_url: Webhook URL
            subject: Alert subject
            message: Alert message
        """
        # Mock implementation - in real code, would make HTTP POST
        print(f"WEBHOOK ALERT to {webhook_url}: {subject}\n{message}")
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring:
            try:
                usage = self.get_team_usage()
                self._check_alerts(usage)
                
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
            
            time.sleep(self.check_interval)
    
    def start(self) -> None:
        """Start monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def stop(self) -> None:
        """Stop monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join()
    
    def get_usage_history(self, hours: int = 24) -> List[TeamUsage]:
        """Get usage history.
        
        Args:
            hours: Number of hours of history to return
            
        Returns:
            List of usage snapshots
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [
            u for u in self._usage_history
            if hasattr(u, 'timestamp') and u.timestamp > cutoff
        ]
    
    def list_alerts(self) -> List[Alert]:
        """List all alerts.
        
        Returns:
            List of alerts
        """
        return list(self._alerts.values())