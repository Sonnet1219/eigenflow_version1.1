"""
Utility functions and tools for the multi-agent system.

Contains helper functions for:
- Database schema creation  
- Chat functionality
- General utility functions
"""

import os
import logging
import asyncio
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import requests
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage


logger = logging.getLogger(__name__)


@tool  
def chat_response(message: str) -> str:
    """Provide helpful chat responses for general questions and conversations."""
    # This could be enhanced to call external APIs or knowledge bases
    return f"I understand you're asking about: '{message}'. I'm here to help you with any questions or conversations you'd like to have. How can I assist you further?"
import requests


logger = logging.getLogger(__name__)


def get_margin_check_report() -> Dict[str, Any]:
    """Simulate LP margin check report generation."""
    # Simulate margin data retrieval
    mock_margin_data = {
        "account_id": "LP_001",
        "total_margin": 150000.0,
        "used_margin": 45000.0,
        "free_margin": 105000.0,
        "margin_level": 333.33,
        "positions": [
            {"pair": "ETH/USDT", "size": 10.5, "margin_used": 25000.0},
            {"pair": "BTC/USDT", "size": 0.8, "margin_used": 20000.0}
        ],
        "timestamp": datetime.now().isoformat(),
        "status": "healthy"
    }
    
    logger.info(f"Generated margin report for account {mock_margin_data['account_id']}")
    return mock_margin_data


def format_margin_report(margin_data: Dict[str, Any]) -> str:
    """Format margin data into a readable report."""
    report = f"""📊 **LP Margin Check Report**
        🔹 **Account Overview**
        - Account ID: {margin_data['account_id']}
        - Total Margin: ${margin_data['total_margin']:,.2f}
        - Used Margin: ${margin_data['used_margin']:,.2f}
        - Free Margin: ${margin_data['free_margin']:,.2f}
        - Margin Level: {margin_data['margin_level']:.2f}%
        - Status: {margin_data['status'].upper()}

        📈 **Active Positions**
    """
    
    for pos in margin_data['positions']:
        report += f"\n- {pos['pair']}: Size {pos['size']}, Margin ${pos['margin_used']:,.2f}"
    
    report += f"\n\n⏰ Report generated at: {margin_data['timestamp']}"
    
    return report


async def chat_response(message: str) -> str:
    """Simple chat response function."""
    # This could be enhanced to call external APIs or knowledge bases
    return f"I understand you said: '{message}'. How can I help you further?"


async def create_schema_if_not_exists(cur) -> None:
    """Create all tables and constraints per db_schema.md (simplified types with identity PK)."""
    await cur.execute(
        """
        CREATE TABLE IF NOT EXISTS margin_check (
            id BIGSERIAL PRIMARY KEY,
            tenant_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            margin FLOAT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """
    )