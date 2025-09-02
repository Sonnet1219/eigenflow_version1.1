"""
Utility functions for the ArXiv data processing pipeline.

Contains helper functions for:
- Database schema creation
"""

import os
import logging
import asyncio
import re
import json
from typing import Dict, Any, List, Optional, Tuple
import requests


logger = logging.getLogger(__name__)


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