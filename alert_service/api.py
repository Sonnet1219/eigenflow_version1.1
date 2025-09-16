"""Alert Service API endpoints."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, BackgroundTasks

# Import data gateway from main project
from src.agent.data_gateway import EigenFlowAPI

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/alert", tags=["alert"])

# Configuration
MONITORING_INTERVAL = 60  # seconds
MARGIN_THRESHOLD = 20  # percentage


class MonitoringService:
    """LP margin monitoring service."""
    
    def __init__(self):
        self.is_running = False
        self.api_client = EigenFlowAPI()
        self.last_alerts = {}  # Track last alert time for each LP
    
    async def monitor_margins(self):
        """Monitor LP margins and log alerts when thresholds are exceeded."""
        self.is_running = True
        logger.info("Starting LP margin monitoring service")
        
        while self.is_running:
            try:
                # Fetch LP account data
                accounts = await self.fetch_lp_data()
                
                alert_triggered = False
                healthy_lps = []
                
                for account in accounts:
                    lp_name = account.get("LP", "Unknown")
                    margin_level = account.get("Margin Utilization %", 0)  # Already in percentage
                    
                    # Check if margin level exceeds threshold
                    if margin_level > MARGIN_THRESHOLD:
                        # Check if we already logged an alert recently (avoid spam)
                        last_alert = self.last_alerts.get(lp_name)
                        now = datetime.now()
                        
                        if not last_alert or (now - last_alert).seconds > MONITORING_INTERVAL:
                            self.last_alerts[lp_name] = now
                            logger.warning(f"🚨 MARGIN ALERT: {lp_name} margin level {margin_level:.2f}% exceeds threshold {MARGIN_THRESHOLD}%")
                            alert_triggered = True
                    else:
                        healthy_lps.append(f"{lp_name} ({margin_level:.2f}%)")
                
                # Report healthy status if no alerts were triggered
                if not alert_triggered and healthy_lps:
                    logger.info(f"✅ All LPs healthy: {', '.join(healthy_lps)} - all below {MARGIN_THRESHOLD}% threshold")
                
                # Wait before next check
                await asyncio.sleep(MONITORING_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(MONITORING_INTERVAL)
    
    async def fetch_lp_data(self) -> List[Dict[str, Any]]:
        """Fetch LP account data from Data Gateway."""
        try:
            # Authenticate if needed
            if not self.api_client.access_token:
                auth_result = self.api_client.authenticate()
                if not auth_result.get("success"):
                    logger.error(f"Authentication failed: {auth_result.get('error')}")
                    return []
            
            # Fetch account data
            accounts_result = self.api_client.get_lp_accounts()
            return accounts_result if isinstance(accounts_result, list) else []
            
        except Exception as e:
            logger.error(f"Error fetching LP data: {e}")
            return []
    
    
    def stop_monitoring(self):
        """Stop the monitoring service."""
        self.is_running = False
        logger.info("LP margin monitoring service stopped")


# Global monitoring service instance
monitoring_service = MonitoringService()


@router.post("/start-monitoring")
async def start_monitoring(background_tasks: BackgroundTasks):
    """Start the LP margin monitoring service."""
    if not monitoring_service.is_running:
        background_tasks.add_task(monitoring_service.monitor_margins)
        return {"status": "success", "message": "Monitoring service started"}
    else:
        return {"status": "info", "message": "Monitoring service already running"}


@router.post("/stop-monitoring")
async def stop_monitoring():
    """Stop the LP margin monitoring service."""
    monitoring_service.stop_monitoring()
    return {"status": "success", "message": "Monitoring service stopped"}


@router.get("/monitoring-status")
async def get_monitoring_status():
    """Get current monitoring service status."""
    return {
        "status": "running" if monitoring_service.is_running else "stopped",
        "threshold": MARGIN_THRESHOLD,
        "interval": MONITORING_INTERVAL,
        "last_alerts": {
            lp: alert_time.isoformat() 
            for lp, alert_time in monitoring_service.last_alerts.items()
        }
    }


@router.post("/test-alert")
async def test_alert(lp_name: str = "TEST_LP", margin_level: float = 85.0):
    """Test alert functionality by logging a test alert."""
    logger.warning(f"🚨 TEST ALERT: {lp_name} margin level {margin_level:.2f}% exceeds threshold {MARGIN_THRESHOLD}%")
    return {
        "status": "success",
        "message": f"Test alert logged for {lp_name}"
    }
