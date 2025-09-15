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
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import requests
from langchain_core.tools import tool
import dotenv
import uuid

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

# Configuration Settings
CONFIG = {
    # Risk thresholds (standardized)
    'MARGIN_ALERT_THRESHOLD': 80.0,  # Standard margin utilization alert threshold
    
    # Analysis parameters
    'LOW_RISK_MULTIPLIER': 0.7,  # For determining low-risk LPs
    'SIGNIFICANT_MARGIN_THRESHOLD': 10000.0,  # Minimum margin to consider for moves
    'CROSS_MARGIN_THRESHOLD': 5000.0,  # Minimum margin release for cross recommendations
    'MOVE_VOLUME_RATIO': 0.5,  # Maximum percentage of position to move
    'MAX_MOVE_VOLUME': 100.0,  # Maximum volume to move in lots
    
    # Data freshness
    'DATA_DEGRADED_THRESHOLD_SEC': 300,  # 5 minutes
    
    # Default values
    'DEFAULT_LEVERAGE': 100.0,
    'DEFAULT_PRICE': 0.0,
    'DEFAULT_SWAP': 0.0,
    
    # Confidence scores
    'CROSS_RECOMMENDATION_CONFIDENCE': 0.85,
    'MOVE_RECOMMENDATION_CONFIDENCE': 0.75,
    
    # Estimated impacts
    'ESTIMATED_MARGIN_REDUCTION': 5000.0,
    
    # API timeouts
    'API_TIMEOUT_SECONDS': 30,
    
    # Schema and formatting
    'SCHEMA_VERSION': 'dc/v1-lean',
    'MONEY_PRECISION': 2,
    'PRICE_PRECISION': 5
}

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
            
            response = requests.post(AUTH_ENDPOINT, json=auth_data, headers=self.headers, timeout=CONFIG['API_TIMEOUT_SECONDS'])
            
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
            response = requests.get(LP_ACCOUNT_ENDPOINT, params=params, headers=self.headers, timeout=CONFIG['API_TIMEOUT_SECONDS'])
            
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
            response = requests.get(LP_POSITION_ENDPOINT, headers=self.headers, timeout=CONFIG['API_TIMEOUT_SECONDS'])
            
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
def get_lp_margin_check() -> str:
    """
    Get comprehensive LP margin and risk data from EigenFlow API.
    
    This tool performs a complete pipeline:
    1. Authenticates with the API
    2. Retrieves LP account information
    3. Fetches current positions
    4. Returns structured JSON data for analysis
    
    Returns structured JSON containing accounts, balances, positions, risk indicators, and metadata.
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
        
        # Step 4: Generate structured JSON data
        account_data = account_result["data"]
        position_data = position_result["data"]
        
        # Generate analysis and return MarginCheckToolResponse format
        margin_response = generate_margin_analysis(account_data, position_data)
        return json.dumps(margin_response, indent=2)
        
    except Exception as e:
        logger.error(f"LP margin report generation failed: {e}")
        return f"❌ Report generation failed: {str(e)}"


def lp_margin_check_report(lp_account_info):
    """
    Check LP margin utilization and generate alerts for accounts >= 80% usage.
    
    Args:
        lp_account_info: List of LP account info dictionaries containing
                        'Margin Utilization %' and 'LP' fields.
    
    Returns:
        List of dictionaries with alert status, LP name, message, and account data.
    """
    result = []

    for info in lp_account_info:
        margin_util = info.get('Margin Utilization %', 0)
        lp_name = info.get('LP', 'Unknown')
        
        if margin_util >= CONFIG['MARGIN_ALERT_THRESHOLD']:
            result.append({
                "is_alert": 1,
                "lp": lp_name,
                "message": "Margin level 80% reached, please watch out.",
                "account_data": info
            })
        else:
            result.append({
                "is_alert": 0,
                "lp": lp_name,
                "message": "Current margin under safe line. No further action needed",
                "account_data": info
            })

    return result


def generate_margin_analysis(account_data: Any, position_data: Any) -> Dict[str, Any]:
    """Generate margin analysis in MarginCheckToolResponse format."""
    
    # Ensure data is in list format for processing
    accounts = account_data if isinstance(account_data, list) else [account_data]
    positions = position_data if isinstance(position_data, list) else [position_data]
    
    current_time = datetime.now()
    trace_id = str(uuid.uuid4())
    
    # Initialize MarginCheckToolResponse structure
    per_lp_metrics = []
    cross_candidates = []
    move_candidates = []
    recommendations = []
    
    # Calculate portfolio-wide metrics
    total_equity = 0
    total_margin = 0
    lp_margin_levels = []
    
    # Process account data for per-LP metrics
    for account in accounts:
        lp_name = account.get("LP", "Unknown")
        balance = account.get("Balance", 0)
        equity = account.get("Equity", 0)
        margin = account.get("Margin", 0)
        free_margin = account.get("Free Margin", 0)
        margin_util = account.get("Margin Utilization %", 0)
        
        total_equity += equity
        total_margin += margin
        lp_margin_levels.append(margin_util)
        
        # Generate alert status using standard function
        alert_result = lp_margin_check_report([account])[0]
        
        # Build per-LP metrics
        per_lp_metrics.append({
            "lp": lp_name,
            "equity": float(equity),
            "marginUsed": float(margin),
            "marginLevel": float(margin_util),
            "thresholdsRef": {
                "warn": CONFIG['MARGIN_ALERT_THRESHOLD'],
                "critical": CONFIG['MARGIN_ALERT_THRESHOLD']
            },
            "topPositionsKey": [],  # Will be populated from position data
            "alertStatus": alert_result["is_alert"],
            "alertMessage": alert_result["message"]
        })
    
    # Calculate average margin level
    avg_margin_level = sum(lp_margin_levels) / len(lp_margin_levels) if lp_margin_levels else 0
    
    # Determine overall status
    status = "ok"
    if any(ml >= CONFIG['MARGIN_ALERT_THRESHOLD'] for ml in lp_margin_levels):
        status = "critical"
    
    # Process positions for cross-candidates and move-candidates
    position_by_symbol = {}
    for position in positions:
        symbol = position.get("Symbol", "N/A")
        if symbol == "N/A":
            continue
            
        lp_name = position.get("LP", "Unknown")
        position_size = position.get("Position", 0)
        margin_used = position.get("Margin", 0)
        
        # Skip positions with zero size or zero margin
        if position_size == 0:
            continue
        
        if symbol not in position_by_symbol:
            position_by_symbol[symbol] = []
            
        side = "buy" if float(position_size) > 0 else "sell"
        volume = abs(float(position_size))
        
        position_by_symbol[symbol].append({
            "lp": lp_name,
            "side": side,
            "volume": volume,
            "margin": float(margin_used),
            "position_size": float(position_size)  # Keep original signed position
        })
    
    # Calculate LP-level margin per unit for estimation
    lp_margin_rates = {}
    for account in accounts:
        lp_name = account.get("LP", "Unknown")
        total_margin = account.get("Margin", 0)
        
        # Calculate total position volume for this LP
        lp_positions = [p for p in positions if p.get("LP") == lp_name and p.get("Position", 0) != 0]
        total_volume = sum(abs(p.get("Position", 0)) for p in lp_positions)
        
        if total_volume > 0:
            lp_margin_rates[lp_name] = total_margin / total_volume
        else:
            lp_margin_rates[lp_name] = 0
    
    # Generate cross-position netting candidates
    for symbol, pos_list in position_by_symbol.items():
        for i, pos1 in enumerate(pos_list):
            for pos2 in pos_list[i+1:]:
                # Check if different LPs and opposite sides (buy vs sell)
                if pos1["lp"] != pos2["lp"] and pos1["side"] != pos2["side"]:
                    nettable_vol = min(pos1["volume"], pos2["volume"])
                    if nettable_vol > 0:
                        # Estimate margin for each position using LP margin rate
                        lp1_margin_rate = lp_margin_rates.get(pos1["lp"], 0)
                        lp2_margin_rate = lp_margin_rates.get(pos2["lp"], 0)
                        
                        pos1_estimated_margin = pos1["volume"] * lp1_margin_rate
                        pos2_estimated_margin = pos2["volume"] * lp2_margin_rate
                        
                        # Calculate releasable margin (conservative estimate)
                        if pos1_estimated_margin > 0 and pos2_estimated_margin > 0:
                            # Margin released = smaller position's margin * netting ratio
                            releasable_margin = min(pos1_estimated_margin, pos2_estimated_margin) * (nettable_vol / max(pos1["volume"], pos2["volume"]))
                        else:
                            releasable_margin = 0
                        
                        cross_candidates.append({
                            "symbol": symbol,
                            "lpA": pos1["lp"],
                            "lpB": pos2["lp"],
                            "volumePair": {"a": pos1["volume"], "b": pos2["volume"]},
                            "releasableMargin": round(releasable_margin, 2)
                        })
    
    # Generate move candidates (high-risk to low-risk LPs)
    high_risk_lps = [lp["lp"] for lp in per_lp_metrics if lp["marginLevel"] >= CONFIG['MARGIN_ALERT_THRESHOLD']]
    low_risk_lps = [lp["lp"] for lp in per_lp_metrics if lp["marginLevel"] < CONFIG['MARGIN_ALERT_THRESHOLD'] * CONFIG['LOW_RISK_MULTIPLIER']]
    
    for high_lp in high_risk_lps:
        for low_lp in low_risk_lps:
            for symbol, pos_list in position_by_symbol.items():
                high_positions = [p for p in pos_list if p["lp"] == high_lp]
                if high_positions:
                    pos = high_positions[0]
                    move_volume = min(pos["volume"] * CONFIG['MOVE_VOLUME_RATIO'], CONFIG['MAX_MOVE_VOLUME'])
                    if move_volume > 0:
                        move_candidates.append({
                            "fromLP": high_lp,
                            "toLP": low_lp,
                            "symbol": symbol,
                            "volume": move_volume,
                            "rationale": "Better margin utilization at target LP"
                        })
    
    # Generate recommendations - only for cross opportunities with actual margin savings
    rec_id = 1
    # Sort cross candidates by releasable margin (highest first)
    sorted_cross_candidates = sorted(cross_candidates, key=lambda x: x['releasableMargin'], reverse=True)
    
    for cross in sorted_cross_candidates[:3]:  # Top 3 cross opportunities
        # Only generate recommendations for meaningful margin savings
        if cross['releasableMargin'] > CONFIG.get('MIN_RELEASABLE_MARGIN', 100):  # Minimum $100 savings
            # Calculate actual impact on margin level
            total_portfolio_margin = sum(account.get("Margin", 0) for account in accounts)
            if total_portfolio_margin > 0:
                ml_improvement = (cross['releasableMargin'] / total_portfolio_margin) * 100
                ml_after = max(0, avg_margin_level - ml_improvement)
            else:
                ml_after = avg_margin_level
            
            recommendations.append({
                "id": f"REC-{rec_id:03d}",
                "type": "CLEAR_CROSS",
                "priority": 1 if cross['releasableMargin'] > 1000 else 2,  # High priority for >$1000 savings
                "impact": {
                    "mlBefore": round(avg_margin_level, 2),
                    "mlAfter": round(ml_after, 2)
                },
                "explain": {
                    "whyNow": f"Cross-netting {cross['symbol']} positions can release ${cross['releasableMargin']:,.0f} margin",
                    "drivers": [{"k": "marginUsed", "delta": -cross['releasableMargin']}],
                    "confidence": CONFIG['CROSS_RECOMMENDATION_CONFIDENCE']
                },
                "actions": [{
                    "tool": "execute_cross_netting",
                    "params": {"symbol": cross['symbol'], "lpA": cross['lpA'], "lpB": cross['lpB']},
                    "idempotencyKey": f"NET-{cross['symbol']}-{current_time.strftime('%Y%m%d')}-{rec_id:03d}"
                }]
            })
            rec_id += 1
    
    # Build final MarginCheckToolResponse
    margin_response = {
        "schemaVer": "dc/v1",
        "status": status,
        "metrics": {
            "avgMarginLevel": round(avg_margin_level, 2),
            "lpCount": len(per_lp_metrics)
        },
        "normalization": {
            "money": "USD",
            "volume": "lot",
            "marginLevelFormat": "percent",
            "spreadDefinition": "price_diff",
            "swapPeriod": "day",
            "rounding": {"money": CONFIG['MONEY_PRECISION'], "priceDefaultScale": CONFIG['PRICE_PRECISION']}
        },
        "perLP": per_lp_metrics,
        "crossCandidates": cross_candidates,
        "moveCandidates": move_candidates,
        "recommendations": recommendations,
        "traceId": trace_id
    }
    
    return margin_response

