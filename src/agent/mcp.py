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
    """Generate detailed margin and risk analysis report with actionable recommendations."""
    
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
    
    
    # Risk summary with enhanced recommendation engine
    overall_util = (total_margin / total_equity * 100) if total_equity > 0 else 0
    
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
    • Overall Margin Utilization: {overall_util:.2f}%

    🎯 **Risk Assessment:**"""
    
    if risk_alerts:
        report += "\n"
        for alert in risk_alerts:
            report += f"   {alert}\n"
    else:
        report += "\n   ✅ All positions within acceptable risk parameters"
    
    # Generate risk level and actionable recommendations
    if overall_util > 75:
        risk_level = "🔴 HIGH RISK"
        recommendations = generate_actionable_recommendations(accounts, positions, overall_util)
        report += f"""
    💡 **Overall Risk Level:** {risk_level}
    
    <MARGIN_ANALYSIS_REPORT>
    {format_margin_analysis_section(accounts, positions, overall_util)}
    </MARGIN_ANALYSIS_REPORT>
    
    <ACTIONABLE_RECOMMENDATIONS>
    {recommendations}
    </ACTIONABLE_RECOMMENDATIONS>"""
    elif overall_util > 50:
        risk_level = "� MODERATE RISK"
        recommendations = generate_actionable_recommendations(accounts, positions, overall_util)
        report += f"""
    💡 **Overall Risk Level:** {risk_level}
    
    <MARGIN_ANALYSIS_REPORT>
    {format_margin_analysis_section(accounts, positions, overall_util)}
    </MARGIN_ANALYSIS_REPORT>
    
    <ACTIONABLE_RECOMMENDATIONS>
    {recommendations}
    </ACTIONABLE_RECOMMENDATIONS>"""
    else:
        risk_level = "🟢 LOW RISK"
        report += f"""
    💡 **Overall Risk Level:** {risk_level}
    
    <MARGIN_ANALYSIS_REPORT>
    {format_margin_analysis_section(accounts, positions, overall_util)}
    </MARGIN_ANALYSIS_REPORT>"""

    report += f"""
    
    {'='*50}
    Report completed successfully ✅
    """
    
    return report


def format_margin_analysis_section(accounts: list, positions: list, overall_util: float) -> str:
    """Format the margin analysis section with detailed metrics."""
    analysis = "## Margin Health Analysis\n\n"
    
    if overall_util > 80:
        analysis += "🚨 **CRITICAL**: Margin utilization exceeds 80% - immediate action required\n"
    elif overall_util > 75:
        analysis += "⚠️ **HIGH RISK**: Margin utilization exceeds 75% - action recommended\n"
    elif overall_util > 50:
        analysis += "⚡ **MODERATE RISK**: Margin utilization above 50% - monitor closely\n"
    else:
        analysis += "✅ **HEALTHY**: Margin utilization within acceptable range\n"
    
    # Add detailed account breakdown
    analysis += "\n### Account Breakdown:\n"
    for account in accounts:
        lp_name = account.get("LP", "Unknown")
        margin_util = account.get("Margin Utilization %", 0)
        equity = account.get("Equity", 0)
        margin = account.get("Margin", 0)
        
        status_emoji = "🔴" if margin_util > 80 else "🟡" if margin_util > 60 else "🟢"
        analysis += f"- **{lp_name}**: {status_emoji} {margin_util:.1f}% utilization (${margin:,.0f} / ${equity:,.0f})\n"
    
    return analysis


def generate_actionable_recommendations(accounts: list, positions: list, overall_util: float) -> str:
    """Generate prioritized actionable recommendations for margin optimization."""
    if overall_util <= 50:
        return "### No immediate action required\n✅ Current margin levels are within acceptable parameters."
    
    recommendations = []
    
    # Analyze positions for cross-LP hedge opportunities (P0 priority)
    cross_hedge_recs = analyze_cross_hedge_opportunities(positions)
    recommendations.extend(cross_hedge_recs)
    
    # Analyze position rebalancing opportunities (P1 priority)
    rebalance_recs = analyze_position_rebalancing(accounts, positions)
    recommendations.extend(rebalance_recs)
    
    # Capital injection recommendations (P2 priority)
    capital_recs = analyze_capital_requirements(accounts, overall_util)
    recommendations.extend(capital_recs)
    
    if not recommendations:
        return "### Manual Review Required\n� No automated recommendations available. Please review positions manually."
    
    # Format recommendations with priority labels
    formatted_recs = "### Priority-Based Action Plan\n\n"
    for i, rec in enumerate(recommendations):
        formatted_recs += f"{rec}\n\n"
    
    return formatted_recs


def analyze_cross_hedge_opportunities(positions: list) -> list:
    """Analyze positions for cross-LP hedge clearing opportunities (P0 priority)."""
    recommendations = []
    
    # Group positions by symbol to find potential hedges
    symbol_groups = {}
    for position in positions:
        symbol = position.get("Symbol", "N/A")
        if symbol == "N/A":
            continue
            
        if symbol not in symbol_groups:
            symbol_groups[symbol] = []
        symbol_groups[symbol].append(position)
    
    priority_counter = 0
    
    # Look for opposing positions across different LPs
    for symbol, symbol_positions in symbol_groups.items():
        if len(symbol_positions) < 2:
            continue
            
        # Find potential hedge pairs
        for i, pos1 in enumerate(symbol_positions):
            for pos2 in symbol_positions[i+1:]:
                lp1 = pos1.get("LP", "")
                lp2 = pos2.get("LP", "")
                size1 = pos1.get("Position", 0)
                size2 = pos2.get("Position", 0)
                margin1 = pos1.get("Margin", 0)
                margin2 = pos2.get("Margin", 0)
                
                # Skip if same LP or invalid data
                if lp1 == lp2 or size1 == "N/A" or size2 == "N/A":
                    continue
                
                # Check if positions are offsetting (opposite signs)
                try:
                    size1_float = float(size1) if isinstance(size1, (int, float, str)) else 0
                    size2_float = float(size2) if isinstance(size2, (int, float, str)) else 0
                    
                    if (size1_float > 0 and size2_float < 0) or (size1_float < 0 and size2_float > 0):
                        # Calculate potential margin release
                        smaller_size = min(abs(size1_float), abs(size2_float))
                        estimated_margin_release = (margin1 + margin2) * (smaller_size / (abs(size1_float) + abs(size2_float)))
                        
                        recommendations.append(
                            f"**(P{priority_counter})** Clear cross-LP hedge on **{symbol}** "
                            f"({abs(smaller_size):.0f} lots) between {lp1} and {lp2}. "
                            f"Expected to release **${estimated_margin_release:,.0f}** margin."
                        )
                        priority_counter += 1
                        
                except (ValueError, TypeError):
                    continue
    
    return recommendations


def analyze_position_rebalancing(accounts: list, positions: list) -> list:
    """Analyze position rebalancing opportunities between LPs (P1 priority)."""
    recommendations = []
    
    # Find accounts with high utilization and those with capacity
    high_util_accounts = []
    low_util_accounts = []
    
    for account in accounts:
        margin_util = account.get("Margin Utilization %", 0)
        lp_name = account.get("LP", "Unknown")
        free_margin = account.get("Free Margin", 0)
        
        if margin_util > 70:
            high_util_accounts.append((lp_name, margin_util, free_margin))
        elif margin_util < 40 and free_margin > 10000:  # Has capacity for more positions
            low_util_accounts.append((lp_name, margin_util, free_margin))
    
    priority_counter = len([r for r in recommendations if r.startswith("**(P")]) if recommendations else 0
    
    # Suggest rebalancing from high to low utilization accounts
    for high_lp, high_util, high_free in high_util_accounts:
        for low_lp, low_util, low_free in low_util_accounts:
            if high_lp != low_lp:
                # Find largest position in high utilization account
                largest_position = None
                largest_margin = 0
                
                for position in positions:
                    if position.get("LP") == high_lp:
                        margin = position.get("Margin", 0)
                        if margin > largest_margin:
                            largest_margin = margin
                            largest_position = position
                
                if largest_position and largest_margin > 5000:  # Minimum threshold
                    symbol = largest_position.get("Symbol", "Unknown")
                    size = largest_position.get("Position", 0)
                    move_size = min(abs(float(size)) * 0.3, 50) if size != "N/A" else 20  # Move 30% or max 50 lots
                    
                    recommendations.append(
                        f"**(P{priority_counter})** Margin level is still high. Consider moving "
                        f"**{move_size:.0f} lots** of **{symbol}** from **{high_lp}** to **{low_lp}**. "
                        f"This could reduce {high_lp}'s utilization by ~{(largest_margin * 0.3 / high_free * 100) if high_free > 0 else 5:.1f}%."
                    )
                    priority_counter += 1
                    break  # Only suggest one rebalancing per high-util account
    
    return recommendations


def analyze_capital_requirements(accounts: list, overall_util: float) -> list:
    """Analyze capital injection requirements (P2 priority)."""
    recommendations = []
    priority_counter = len([r for r in recommendations if r.startswith("**(P")]) if recommendations else 0
    
    if overall_util > 80:
        # Calculate required capital injection
        total_equity = sum(account.get("Equity", 0) for account in accounts)
        total_margin = sum(account.get("Margin", 0) for account in accounts)
        
        # Target 60% utilization
        target_util = 60.0
        required_equity = total_margin / (target_util / 100)
        additional_capital = required_equity - total_equity
        
        if additional_capital > 0:
            # Find account with highest utilization for capital injection
            highest_util_account = max(accounts, key=lambda x: x.get("Margin Utilization %", 0))
            lp_name = highest_util_account.get("LP", "Unknown")
            
            recommendations.append(
                f"**(P{priority_counter})** Consider capital injection of **${additional_capital:,.0f}** "
                f"into **{lp_name}** to bring overall utilization to {target_util}%. "
                f"This will provide additional safety margin for position management."
            )
    
    return recommendations