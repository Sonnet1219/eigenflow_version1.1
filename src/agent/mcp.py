"""
Real API integration tools for LP margin checking and risk analysis.

Contains tools for:
- Authentication with EigenFlow API
- LP account information retrieval
- LP position data fetching
- Risk analysis and reporting
"""

import os
import logging
from typing import Dict, Any, List, Optional
import requests
from datetime import datetime
from langchain_core.tools import tool
import dotenv

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

# API Configuration
API_BASE_URL = "https://api-anshin.sigmarisk.com.au/api/v1"
AUTH_ENDPOINT = f"{API_BASE_URL}/auth"
LP_ACCOUNT_ENDPOINT = f"{API_BASE_URL}/lp/account"
LP_POSITION_ENDPOINT = f"{API_BASE_URL}/lp/position"


class EigenFlowAPI:
    """EigenFlow API client for LP data retrieval."""
    
    def __init__(self):
        self.access_token = None
        self.headers = {"Content-Type": "application/json"}
    
    def authenticate(self, email: str = None, password: str = None, broker: str = None) -> Dict[str, Any]:
        """Authenticate with EigenFlow API and get access token."""
        # Use environment variables if credentials not provided
        email = email or os.getenv("EIGENFLOW_EMAIL")
        password = password or os.getenv("EIGENFLOW_PASSWORD") 
        broker = broker or os.getenv("EIGENFLOW_BROKER")
        
        if not email or not password or not broker:
            return {
                "success": False, 
                "error": "Email, password and broker required. Set EIGENFLOW_EMAIL, EIGENFLOW_PASSWORD and EIGENFLOW_BROKER env vars."
            }
        
        try:
            auth_data = {
                "email": email,
                "password": password,
                "broker": broker  # Use the pre-hashed broker value directly
            }
            
            response = requests.post(AUTH_ENDPOINT, json=auth_data, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                auth_result = response.json()
                self.access_token = auth_result.get("access_token")
                
                if self.access_token:
                    # Update headers with authorization
                    self.headers["Authorization"] = f"Bearer {self.access_token}"
                    logger.info("Successfully authenticated with EigenFlow API")
                    return {"success": True, "message": "Authentication successful"}
                else:
                    return {"success": False, "error": "No access token received"}
            else:
                return {
                    "success": False, 
                    "error": f"Authentication failed: {response.status_code} - {response.text}"
                }
                
        except requests.RequestException as e:
            logger.error(f"Authentication request failed: {e}")
            return {"success": False, "error": f"Request failed: {str(e)}"}
            
            response = requests.post(AUTH_ENDPOINT, json=auth_data, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                auth_result = response.json()
                self.access_token = auth_result.get("access_token")
                
                if self.access_token:
                    # Update headers with authorization
                    self.headers["Authorization"] = f"Bearer {self.access_token}"
                    logger.info("Successfully authenticated with EigenFlow API")
                    return {"success": True, "message": "Authentication successful"}
                else:
                    return {"success": False, "error": "No access token received"}
            else:
                return {
                    "success": False, 
                    "error": f"Authentication failed: {response.status_code} - {response.text}"
                }
                
        except requests.RequestException as e:
            logger.error(f"Authentication request failed: {e}")
            return {"success": False, "error": f"Request failed: {str(e)}"}
    
    def get_lp_account(self, lp_id: Optional[int] = None) -> Dict[str, Any]:
        """Get LP account information."""
        if not self.access_token:
            return {"success": False, "error": "Not authenticated. Please login first."}
        
        try:
            params = {"lp_id": lp_id} if lp_id else {}
            response = requests.get(LP_ACCOUNT_ENDPOINT, params=params, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                account_data = response.json()
                logger.info(f"Retrieved LP account data: {len(account_data) if isinstance(account_data, list) else 1} accounts")
                return {"success": True, "data": account_data}
            else:
                return {
                    "success": False,
                    "error": f"Failed to get account data: {response.status_code} - {response.text}"
                }
                
        except requests.RequestException as e:
            logger.error(f"LP account request failed: {e}")
            return {"success": False, "error": f"Request failed: {str(e)}"}
    
    def get_lp_positions(self) -> Dict[str, Any]:
        """Get LP position information."""
        if not self.access_token:
            return {"success": False, "error": "Not authenticated. Please login first."}
        
        try:
            response = requests.get(LP_POSITION_ENDPOINT, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                position_data = response.json()
                logger.info(f"Retrieved LP position data: {len(position_data) if isinstance(position_data, list) else 1} positions")
                return {"success": True, "data": position_data}
            else:
                return {
                    "success": False,
                    "error": f"Failed to get position data: {response.status_code} - {response.text}"
                }
                
        except requests.RequestException as e:
            logger.error(f"LP position request failed: {e}")
            return {"success": False, "error": f"Request failed: {str(e)}"}


# Global API client instance
api_client = EigenFlowAPI()


@tool
def get_lp_margin_report() -> str:
    """
    Get comprehensive LP margin and risk analysis report from EigenFlow API.
    
    This tool performs a complete pipeline:
    1. Authenticates with the API
    2. Retrieves LP account information
    3. Fetches current positions
    4. Generates risk analysis report
    
    Returns detailed margin report with risk analysis.
    """
    try:
        # Step 1: Authenticate
        auth_result = api_client.authenticate()
        if not auth_result["success"]:
            return f"❌ Authentication failed: {auth_result['error']}"
        
        # Step 2: Get LP account data
        account_result = api_client.get_lp_account()
        if not account_result["success"]:
            return f"❌ Failed to retrieve account data: {account_result['error']}"
        
        # Step 3: Get LP positions
        position_result = api_client.get_lp_positions()
        if not position_result["success"]:
            return f"❌ Failed to retrieve position data: {position_result['error']}"
        
        # Step 4: Generate comprehensive report
        account_data = account_result["data"]
        position_data = position_result["data"]
        
        report = generate_margin_risk_report(account_data, position_data)
        return report
        
    except Exception as e:
        logger.error(f"LP margin report generation failed: {e}")
        return f"❌ Report generation failed: {str(e)}"


def generate_margin_risk_report(account_data: Any, position_data: Any) -> str:
    """Generate detailed margin and risk analysis report."""
    
    # Ensure data is in list format for processing
    accounts = account_data if isinstance(account_data, list) else [account_data]
    positions = position_data if isinstance(position_data, list) else [position_data]
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report = f"""📊 **LP Margin & Risk Analysis Report**
    Generated at: {current_time}

    {'='*50}
    🏦 **ACCOUNT OVERVIEW**
    {'='*50}
    """
    
    total_equity = 0
    total_margin = 0
    total_free_margin = 0
    risk_alerts = []
    
    # Process account data
    for i, account in enumerate(accounts, 1):
        lp_name = account.get("LP", "Unknown")
        balance = account.get("Balance", 0)
        equity = account.get("Equity", 0)
        margin = account.get("Margin", 0)
        free_margin = account.get("Free Margin", 0)
        margin_util = account.get("Margin Utilization %", 0)
        unrealized_pnl = account.get("Unrealized P&L", 0)
        
        total_equity += equity
        total_margin += margin
        total_free_margin += free_margin
        
        report += f"""
        📈 Account {i}: {lp_name}
        • Balance: ${balance:,.2f}
        • Equity: ${equity:,.2f}
        • Margin Used: ${margin:,.2f}
        • Free Margin: ${free_margin:,.2f}
        • Margin Utilization: {margin_util:.2f}%
        • Unrealized P&L: ${unrealized_pnl:,.2f}
        """
        
        # Risk analysis
        if margin_util > 80:
            risk_alerts.append(f"⚠️ HIGH RISK: {lp_name} margin utilization at {margin_util:.1f}%")
        elif margin_util > 60:
            risk_alerts.append(f"⚡ MEDIUM RISK: {lp_name} margin utilization at {margin_util:.1f}%")
        
        if unrealized_pnl < -1000:
            risk_alerts.append(f"📉 LOSS ALERT: {lp_name} unrealized loss of ${abs(unrealized_pnl):,.2f}")
    
    # Position analysis
    report += f"""
    {'='*50}
    📋 **POSITION DETAILS**
    {'='*50}
    """
    
    position_count = len(positions)
    total_position_value = 0
    
    for i, position in enumerate(positions, 1):
        lp_name = position.get("LP", "Unknown")
        symbol = position.get("Symbol", "N/A")
        position_size = position.get("Position", 0)
        margin_used = position.get("Margin", 0)
        unrealized_pnl = position.get("Margin Unrealized P&L in Account CCY", 0)
        
        total_position_value += abs(position_size) if position_size != "N/A" else 0
        
        report += f"""
        🔹 Position {i}: {symbol} ({lp_name})
        • Size: {position_size}
        • Margin: ${margin_used:,.2f}
        • Unrealized P&L: ${unrealized_pnl:,.2f}
        """
    
    # Risk summary
    report += f"""
    {'='*50}
    ⚡ **RISK ANALYSIS SUMMARY**
    {'='*50}

    📊 **Portfolio Metrics:**
    • Total Accounts: {len(accounts)}
    • Total Positions: {position_count}
    • Combined Equity: ${total_equity:,.2f}
    • Total Margin Used: ${total_margin:,.2f}
    • Total Free Margin: ${total_free_margin:,.2f}

    🎯 **Risk Assessment:**"""
    
    if risk_alerts:
        report += "\n"
        for alert in risk_alerts:
            report += f"   {alert}\n"
    else:
        report += "\n   ✅ All positions within acceptable risk parameters"
    
    # Overall risk level
    overall_util = (total_margin / total_equity * 100) if total_equity > 0 else 0
    
    if overall_util > 75:
        risk_level = "🔴 HIGH RISK"
        recommendation = "Consider reducing position sizes or adding capital"
    elif overall_util > 50:
        risk_level = "🟡 MODERATE RISK"  
        recommendation = "Monitor positions closely"
    else:
        risk_level = "🟢 LOW RISK"
        recommendation = "Risk levels acceptable"
    
    report += f"""
    💡 **Overall Risk Level:** {risk_level}
    📝 **Recommendation:** {recommendation}

    {'='*50}
    Report completed successfully ✅
    """
    
    return report