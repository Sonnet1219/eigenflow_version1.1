"""Alert Service API endpoints."""

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, Any, List, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field

# Import data gateway from main project
from src.agent.data_gateway import EigenFlowAPI

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/alert", tags=["alert"])

# Configuration
MONITORING_INTERVAL = 60  # seconds
ALERT_TRIGGER_THRESHOLD = float(os.getenv("ALERT_TRIGGER_THRESHOLD", "30"))  # percentage
ALERT_RESOLVE_THRESHOLD = float(os.getenv("ALERT_RESOLVE_THRESHOLD", "25"))  # percentage
NOTIFICATION_INITIAL_WINDOW = int(os.getenv("ALERT_INITIAL_WINDOW_SECONDS", "300"))  # first 5 minutes
NOTIFICATION_INITIAL_FREQUENCY = int(os.getenv("ALERT_INITIAL_FREQUENCY_SECONDS", "60"))
NOTIFICATION_COOLDOWN_FREQUENCY = int(os.getenv("ALERT_COOLDOWN_FREQUENCY_SECONDS", "900"))
MARGIN_CHECK_URL = os.getenv("MARGIN_CHECK_URL", "http://0.0.0.0:8001/agent/margin-check")
MARGIN_RECHECK_URL = os.getenv("MARGIN_RECHECK_URL", "http://0.0.0.0:8001/agent/margin-check/recheck")
MARGIN_ENDPOINT_TIMEOUT = float(os.getenv("MARGIN_ENDPOINT_TIMEOUT", "100"))

class AlertStatus(str, Enum):
    """Enumeration of alert card lifecycle states."""

    NEW = "new"
    AWAITING_HITL = "awaiting_hitl"
    PENDING_RECHECK = "pending_recheck"
    IGNORED = "ignored"
    COMPLETED = "completed"
    OVERRIDDEN = "overridden"


@dataclass
class AlertCard:
    """Representation of a margin alert card and its lifecycle data."""

    id: str
    lp_name: str
    threshold: float
    hysteresis_threshold: float
    created_at: datetime
    updated_at: datetime
    status: AlertStatus
    margin_level: float
    last_margin_snapshot: Dict[str, Any]
    reports: List[Dict[str, Any]] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)
    thread_id: Optional[str] = None
    ignore_until: Optional[datetime] = None
    last_notified_at: Optional[datetime] = None
    notifications_sent: int = 0

    def add_history(self, actor: str, action: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        metadata = metadata or {}
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "actor": actor,
            "action": action,
            "message": message,
            "metadata": metadata,
        }
        self.history.append(event)
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "lp": self.lp_name,
            "status": self.status.value,
            "threshold": self.threshold,
            "hysteresis_threshold": self.hysteresis_threshold,
            "margin_level": self.margin_level,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
            "ignore_until": self.ignore_until.isoformat() + "Z" if self.ignore_until else None,
            "thread_id": self.thread_id,
            "reports": self.reports,
            "history": self.history,
            "last_notified_at": self.last_notified_at.isoformat() + "Z" if self.last_notified_at else None,
            "notifications_sent": self.notifications_sent,
            "last_margin_snapshot": self.last_margin_snapshot,
        }

    def set_status(self, status: AlertStatus) -> None:
        self.status = status
        self.updated_at = datetime.utcnow()


class MonitoringService:
    """LP margin monitoring service with alert card lifecycle management."""
    
    def __init__(self):
        self.is_running = False
        self.api_client = EigenFlowAPI()
        self.last_alerts = {}  # Track last alert time for logging/compatibility
        self.cards: Dict[str, AlertCard] = {}
        self.lp_to_card: Dict[str, str] = {}
        self.card_lock = asyncio.Lock()
    
    async def monitor_margins(self):
        """Monitor LP margins, manage alert cards, and orchestrate notifications."""
        self.is_running = True
        logger.info("Starting LP margin monitoring service")

        while self.is_running:
            try:
                now = datetime.utcnow()
                accounts = await self.fetch_lp_data()

                if not accounts:
                    logger.debug("No account data retrieved during monitoring cycle")

                await self._process_accounts(accounts, now)
                await self._process_notifications(now)

                await asyncio.sleep(MONITORING_INTERVAL)

            except Exception as exc:
                logger.error(f"Error in monitoring loop: {exc}")
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

    async def _process_accounts(self, accounts: List[Dict[str, Any]], now: datetime) -> None:
        """Process account snapshots for alert lifecycle transitions."""
        async with self.card_lock:
            for account in accounts:
                lp_name = account.get("LP", "Unknown")
                margin_level = float(account.get("Margin Utilization %", 0))

                card = self._get_card_for_lp(lp_name)

                if margin_level >= ALERT_TRIGGER_THRESHOLD:
                    if card and card.status == AlertStatus.IGNORED and card.ignore_until and card.ignore_until > now:
                        # Ignore still active, update snapshot only
                        card.margin_level = margin_level
                        card.last_margin_snapshot = account
                        continue

                    if card and card.status in {AlertStatus.AWAITING_HITL, AlertStatus.PENDING_RECHECK, AlertStatus.IGNORED}:
                        # Update existing active card snapshot
                        card.margin_level = margin_level
                        card.last_margin_snapshot = account
                        if card.status == AlertStatus.IGNORED and (not card.ignore_until or card.ignore_until <= now):
                            card.ignore_until = None
                            card.set_status(AlertStatus.AWAITING_HITL)
                            card.add_history(
                                actor="system",
                                action="ignore_expired",
                                message="忽略时段已结束，继续提醒保证金风险",
                                metadata={"margin_level": margin_level},
                            )
                        continue

                    # No active card exists, create new one
                    await self._create_alert_card(lp_name, margin_level, account, now)

                else:
                    if card and card.status not in {AlertStatus.COMPLETED, AlertStatus.OVERRIDDEN}:
                        if margin_level <= ALERT_RESOLVE_THRESHOLD:
                            await self._resolve_card(card, margin_level, now)
                        else:
                            # Within hysteresis band, keep card but update snapshot
                            card.margin_level = margin_level
                            card.last_margin_snapshot = account

    async def _process_notifications(self, now: datetime) -> None:
        """Send scheduled reminders for outstanding alerts while avoiding alert storms."""
        async with self.card_lock:
            for card in self.cards.values():
                if card.status == AlertStatus.AWAITING_HITL:
                    if card.ignore_until and card.ignore_until > now:
                        continue

                    interval = NOTIFICATION_INITIAL_FREQUENCY
                    elapsed = (now - card.created_at).total_seconds()
                    if elapsed > NOTIFICATION_INITIAL_WINDOW:
                        interval = NOTIFICATION_COOLDOWN_FREQUENCY

                    if not card.last_notified_at or (now - card.last_notified_at).total_seconds() >= interval:
                        card.last_notified_at = now
                        card.notifications_sent += 1
                        card.add_history(
                            actor="system",
                            action="notification",
                            message="提醒：保证金风险依旧存在，等待人工处理",
                            metadata={
                                "notification_interval": interval,
                                "margin_level": card.margin_level,
                                "notifications_sent": card.notifications_sent,
                            },
                        )
                        logger.warning(
                            "Notification dispatched for LP %s (card=%s, margin=%.2f%%)",
                            card.lp_name,
                            card.id,
                            card.margin_level,
                        )

    def _get_card_for_lp(self, lp_name: str) -> Optional[AlertCard]:
        card_id = self.lp_to_card.get(lp_name)
        if not card_id:
            return None
        return self.cards.get(card_id)

    async def _create_alert_card(self, lp_name: str, margin_level: float, account_snapshot: Dict[str, Any], now: datetime) -> None:
        """Instantiate a new alert card and trigger initial margin check."""
        card_id = str(uuid.uuid4())
        card = AlertCard(
            id=card_id,
            lp_name=lp_name,
            threshold=ALERT_TRIGGER_THRESHOLD,
            hysteresis_threshold=ALERT_RESOLVE_THRESHOLD,
            created_at=now,
            updated_at=now,
            status=AlertStatus.AWAITING_HITL,
            margin_level=margin_level,
            last_margin_snapshot=account_snapshot,
        )
        card.add_history(
            actor="system",
            action="created",
            message="检测到保证金水平超过阈值，已创建风险卡片",
            metadata={"margin_level": margin_level, "threshold": ALERT_TRIGGER_THRESHOLD},
        )
        self.cards[card_id] = card
        self.lp_to_card[lp_name] = card_id
        self.last_alerts[lp_name] = now

        logger.warning(
            "🚨 MARGIN ALERT: %s margin level %.2f%% exceeds threshold %.2f%% (card=%s)",
            lp_name,
            margin_level,
            ALERT_TRIGGER_THRESHOLD,
            card_id,
        )

        self._schedule_task(
            self._trigger_margin_check(card_id, margin_level),
            f"margin_check_{card_id}",
        )

    async def _resolve_card(self, card: AlertCard, margin_level: float, now: datetime) -> None:
        """Mark card as resolved when margin recovers below hysteresis threshold."""
        card.margin_level = margin_level
        card.last_margin_snapshot = {**card.last_margin_snapshot, "Margin Utilization %": margin_level}
        card.set_status(AlertStatus.COMPLETED)
        card.ignore_until = None
        card.add_history(
            actor="system",
            action="resolved",
            message="风险已解除，保证金回落至安全阈值以下",
            metadata={"margin_level": margin_level},
        )
        logger.info(
            "✅ Margin risk resolved for LP %s (card=%s, margin=%.2f%%)",
            card.lp_name,
            card.id,
            margin_level,
        )

        # Remove mapping so future breaches create new cards
        if card.lp_name in self.lp_to_card:
            del self.lp_to_card[card.lp_name]

    async def _trigger_margin_check(self, card_id: str, margin_level: float) -> None:
        """Invoke margin_check endpoint for a newly created alert card."""
        async with self.card_lock:
            card = self.cards.get(card_id)
            if not card:
                return
            lp_name = card.lp_name

        payload = {
            "eventType": "MARGIN_ALERT",
            "payload": {
                "lp": lp_name,
                "marginLevel": margin_level / 100.0,
                "threshold": ALERT_TRIGGER_THRESHOLD / 100.0,
            },
        }

        response = await self._call_margin_endpoint(MARGIN_CHECK_URL, payload)

        async with self.card_lock:
            card = self.cards.get(card_id)
            if not card:
                return

            report_entry = {
                "type": "initial",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "payload": payload,
                "response": response,
            }
            card.reports.append(report_entry)
            card.thread_id = response.get("thread_id") or card.thread_id
            if response.get("status") == "error":
                card.add_history(
                    actor="system",
                    action="margin_check_failed",
                    message="初始保证金分析生成失败，请检查日志",
                    metadata={"error": response.get("error")},
                )
                card.set_status(AlertStatus.AWAITING_HITL)
            else:
                card.add_history(
                    actor="system",
                    action="margin_check",
                    message="已生成初始保证金分析报告",
                    metadata={"thread_id": card.thread_id},
                )

    async def _trigger_margin_recheck(self, card_id: str) -> None:
        """Invoke margin_check recheck endpoint after human feedback."""
        async with self.card_lock:
            card = self.cards.get(card_id)
            if not card or not card.thread_id:
                return
            card.set_status(AlertStatus.PENDING_RECHECK)

        payload = {"thread_id": card.thread_id}
        response = await self._call_margin_endpoint(MARGIN_RECHECK_URL, payload)

        latest_snapshot = await self._fetch_latest_snapshot(card_id)

        async with self.card_lock:
            card = self.cards.get(card_id)
            if not card:
                return

            report_entry = {
                "type": "recheck",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "payload": payload,
                "response": response,
            }
            card.reports.append(report_entry)
            if response.get("status") == "error":
                card.add_history(
                    actor="system",
                    action="recheck_failed",
                    message="复查调用失败，请人工确认",
                    metadata={"error": response.get("error")},
                )
                card.set_status(AlertStatus.AWAITING_HITL)
                return
            else:
                card.add_history(
                    actor="system",
                    action="recheck",
                    message="已完成复查并生成最新报告",
                    metadata={"thread_id": card.thread_id},
                )

            if latest_snapshot:
                card.margin_level = latest_snapshot["margin_level"]
                card.last_margin_snapshot = latest_snapshot["account"]

            latest_margin = card.margin_level
            if latest_margin <= ALERT_RESOLVE_THRESHOLD:
                await self._resolve_card(card, latest_margin, datetime.utcnow())
            else:
                card.set_status(AlertStatus.AWAITING_HITL)
                card.last_notified_at = datetime.utcnow()
                card.add_history(
                    actor="system",
                    action="recheck_pending",
                    message="复查后风险仍未解除，待人工进一步处理",
                    metadata={"margin_level": latest_margin},
                )

    async def _call_margin_endpoint(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Call external margin endpoints safely with consistent error handling."""
        try:
            async with httpx.AsyncClient(timeout=MARGIN_ENDPOINT_TIMEOUT) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                print("Margin endpoint response:", response.json())
                return response.json()
        except Exception as exc:
            logger.error("Failed to call margin endpoint %s: %s", url, exc)
            return {
                "type": "error",
                "status": "error",
                "error": str(exc),
            }

    def _schedule_task(self, coro, task_name: str) -> None:
        """Schedule a background coroutine and surface exceptions via logging."""
        task = asyncio.create_task(coro, name=task_name)

        def _handle_result(completed_task: asyncio.Task) -> None:
            try:
                completed_task.result()
            except Exception as err:  # pragma: no cover - defensive logging only
                logger.error("Background task %s failed: %s", task_name, err)

        task.add_done_callback(_handle_result)

    async def _fetch_latest_snapshot(self, card_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the most recent account snapshot for the card's LP."""
        async with self.card_lock:
            card = self.cards.get(card_id)
            lp_name = card.lp_name if card else None

        if not lp_name:
            return None

        accounts = await self.fetch_lp_data()
        for account in accounts:
            if account.get("LP") == lp_name:
                margin_level = float(account.get("Margin Utilization %", 0))
                return {"account": account, "margin_level": margin_level}

        logger.warning(
            "Latest account snapshot for LP %s not found while refreshing card %s",
            lp_name,
            card_id,
        )
        return None

    async def list_cards(self) -> List[Dict[str, Any]]:
        async with self.card_lock:
            return [card.to_dict() for card in self.cards.values()]

    async def get_card(self, card_id: str) -> AlertCard:
        async with self.card_lock:
            card = self.cards.get(card_id)
            if not card:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert card not found")
            return card

    async def submit_hitl_feedback(self, card_id: str, decision: str, notes: Optional[str]) -> Dict[str, Any]:
        async with self.card_lock:
            card = self.cards.get(card_id)
            if not card:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert card not found")

            if not card.thread_id:
                card.add_history(
                    actor="system",
                    action="recheck_skipped",
                    message="由于缺少线程信息，无法自动复查，请重新生成报告",
                )
                card.set_status(AlertStatus.AWAITING_HITL)
                return card.to_dict()

            card.add_history(
                actor="human",
                action="hitl_feedback",
                message="人工审核反馈已记录",
                metadata={"decision": decision, "notes": notes},
            )
            card.set_status(AlertStatus.PENDING_RECHECK)

        self._schedule_task(
            self._trigger_margin_recheck(card_id),
            f"margin_recheck_{card_id}",
        )
        return card.to_dict()

    async def ignore_card(self, card_id: str, ignore_until: datetime) -> Dict[str, Any]:
        async with self.card_lock:
            card = self.cards.get(card_id)
            if not card:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert card not found")

            card.ignore_until = ignore_until
            card.set_status(AlertStatus.IGNORED)
            card.add_history(
                actor="human",
                action="ignored",
                message="告警已被暂时忽略",
                metadata={"ignore_until": ignore_until.isoformat() + "Z"},
            )

        return card.to_dict()

    async def override_card(self, card_id: str, status_value: str, reason: Optional[str]) -> Dict[str, Any]:
        async with self.card_lock:
            card = self.cards.get(card_id)
            if not card:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert card not found")

            try:
                status_enum = AlertStatus(status_value)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status value") from exc

            card.set_status(status_enum)
            card.add_history(
                actor="human",
                action="override",
                message="告警状态已被人工覆盖",
                metadata={"new_status": status_enum.value, "reason": reason},
            )

            if status_enum in {AlertStatus.COMPLETED, AlertStatus.OVERRIDDEN} and card.lp_name in self.lp_to_card:
                del self.lp_to_card[card.lp_name]

        return card.to_dict()


# Global monitoring service instance
monitoring_service = MonitoringService()


class HumanFeedbackRequest(BaseModel):
    """Payload for human-in-the-loop feedback submissions."""

    decision: str = Field(..., description="人工决策摘要，例如 approve/reject/adjust")
    notes: Optional[str] = Field(default=None, description="可选的备注信息")


class IgnoreRequest(BaseModel):
    """Payload for temporarily ignoring an alert card."""

    duration_minutes: Optional[int] = Field(
        default=None,
        ge=1,
        description="忽略时长（分钟），与 ignore_until 至少提供一个",
    )
    ignore_until: Optional[datetime] = Field(
        default=None,
        description="忽略截止时间，UTC ISO 格式",
    )


class OverrideRequest(BaseModel):
    """Payload for overriding alert card status manually."""

    status: str = Field(..., description="目标状态，需为 AlertStatus 枚举值")
    reason: Optional[str] = Field(default=None, description="覆盖原因")


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
    cards = await monitoring_service.list_cards()
    status_counts: Dict[str, int] = {}
    for card in cards:
        status_counts[card["status"]] = status_counts.get(card["status"], 0) + 1

    return {
        "status": "running" if monitoring_service.is_running else "stopped",
        "trigger_threshold": ALERT_TRIGGER_THRESHOLD,
        "resolve_threshold": ALERT_RESOLVE_THRESHOLD,
        "interval": MONITORING_INTERVAL,
        "last_alerts": {
            lp: alert_time.isoformat() + "Z"
            for lp, alert_time in monitoring_service.last_alerts.items()
        },
        "cards": {
            "total": len(cards),
            "by_status": status_counts,
        },
    }


@router.get("/cards")
async def list_alert_cards(status: Optional[str] = None, lp: Optional[str] = None):
    """List alert cards with optional status or LP filters."""
    cards = await monitoring_service.list_cards()

    if status:
        cards = [card for card in cards if card["status"] == status]
    if lp:
        cards = [card for card in cards if card["lp"] == lp]

    return {"cards": cards}


@router.get("/cards/{card_id}")
async def get_alert_card(card_id: str):
    """Retrieve full details for a specific alert card."""
    card = await monitoring_service.get_card(card_id)
    return card.to_dict()


@router.post("/cards/{card_id}/hitl")
async def submit_hitl_feedback(card_id: str, payload: HumanFeedbackRequest):
    """Submit human feedback and trigger automated recheck."""
    card_data = await monitoring_service.submit_hitl_feedback(
        card_id, payload.decision, payload.notes
    )
    return card_data


def _resolve_ignore_until(request: IgnoreRequest) -> datetime:
    now = datetime.utcnow()
    if request.ignore_until:
        ignore_until = request.ignore_until
        if ignore_until.tzinfo:
            ignore_until = ignore_until.astimezone(timezone.utc).replace(tzinfo=None)
    elif request.duration_minutes:
        ignore_until = now + timedelta(minutes=request.duration_minutes)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="duration_minutes 或 ignore_until 至少提供一个",
        )

    if ignore_until <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ignore_until 需要晚于当前时间",
        )

    return ignore_until


@router.post("/cards/{card_id}/ignore")
async def ignore_alert_card(card_id: str, payload: IgnoreRequest):
    """Temporarily ignore an alert card without dismissing it."""
    ignore_until = _resolve_ignore_until(payload)
    card_data = await monitoring_service.ignore_card(card_id, ignore_until)
    return card_data


@router.post("/cards/{card_id}/override")
async def override_alert_card(card_id: str, payload: OverrideRequest):
    """Override a card status manually (emergency control)."""
    card_data = await monitoring_service.override_card(
        card_id, payload.status, payload.reason
    )
    return card_data


@router.post("/test-alert")
async def test_alert(lp_name: str = "TEST_LP", margin_level: float = 85.0):
    """Test alert functionality by logging a test alert."""
    logger.warning(
        "🚨 TEST ALERT: %s margin level %.2f%% exceeds threshold %.2f%%",
        lp_name,
        margin_level,
        ALERT_TRIGGER_THRESHOLD,
    )
    return {
        "status": "success",
        "message": f"Test alert logged for {lp_name}"
    }
