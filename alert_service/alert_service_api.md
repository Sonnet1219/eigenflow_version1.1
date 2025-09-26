# Alert Service

独立的告警监控服务，专注于LP保证金监控和告警检测。

## 目录结构

```
alert_service/
├── __init__.py          # 包初始化文件
├── main.py             # 服务启动入口
├── app.py              # FastAPI应用配置
├── api.py              # API端点定义
└── README.md           # 服务说明文档
```

## 启动服务

```bash
# 在项目根目录下运行
python -m alert_service.main
```

服务将在 http://localhost:8002 启动

## API端点

- `GET /` - 服务状态检查
- `GET /health` - 健康检查
- `POST /alert/start-monitoring` - 启动风险监控循环
- `POST /alert/stop-monitoring` - 停止风险监控循环
- `GET /alert/monitoring-status` - 查询监控状态与卡片统计
- `GET /alert/cards` - 列出所有告警卡片
- `GET /alert/cards/{card_id}` - 查看单个卡片详情与历史
- `POST /alert/cards/{card_id}/hitl` - 人工反馈并触发复查
- `POST /alert/cards/{card_id}/ignore` - 在指定时段内忽略告警
- `POST /alert/cards/{card_id}/override` - 人工覆盖卡片状态（暂时在测试中）
- `POST /alert/test-alert` - 模拟生成测试告警（暂时还在测试中）

## 告警卡片生命周期

1. **阈值触发**：监控服务检测到 `margin` 超过触发阈值（默认 90%）时会创建告警卡片，并立刻调用主服务 `/agent/margin-check` 生成初始报告。
2. **等待人工**：卡片状态进入 `awaiting_hitl`，系统按通知策略推送提醒，直到人工处理或风险解除。
3. **人工反馈**：通过 `POST /alert/cards/{id}/hitl` 提交意见，服务调用 `/agent/margin-check/recheck` 获取最新报告。
4. **自动解除**：当 `margin` 回落至恢复阈值（默认 85%）以下时，卡片自动标记为 `completed`，并记录“风险已解除”。
5. **忽略与覆盖**：可通过 `ignore` 暂时静默，也可通过 `override` 强制关闭或重置状态。

所有操作（系统或人工）都会记录在卡片的 `history` 中，方便追溯。

## 服务特性

1. **独立进程**: 运行在8002端口，避免自循环调用问题
2. **外部调用**: 通过HTTP调用主服务(8001端口)的 `/agent/margin-check` 与 `/agent/margin-check/recheck`
3. **生命周期管理**: 内置告警卡片、历史、忽略策略、迟滞阈值等完整逻辑
4. **通知节流**: 前5分钟按1分钟/次提醒，之后降频为15分钟/次，防止告警风暴

## 配置

- `MONITORING_INTERVAL`：监控循环间隔，默认 60 秒
- `ALERT_TRIGGER_THRESHOLD`：触发阈值（百分比），默认 90
- `ALERT_RESOLVE_THRESHOLD`：恢复阈值（百分比），默认 85
- `ALERT_INITIAL_WINDOW_SECONDS`：高频提醒持续时长，默认 300（5 分钟）
- `ALERT_INITIAL_FREQUENCY_SECONDS`：高频提醒间隔，默认 60 秒
- `ALERT_COOLDOWN_FREQUENCY_SECONDS`：降频后的提醒间隔，默认 900 秒（15 分钟）
- `MARGIN_CHECK_URL`：初始报告调用地址，默认 `http://localhost:8000/agent/margin-check`
- `MARGIN_RECHECK_URL`：复查报告调用地址，默认 `http://localhost:8000/agent/margin-check/recheck`
- `MARGIN_ENDPOINT_TIMEOUT`：调用超时时间（秒），默认 30

## 接口文档

### `POST /alert/start-monitoring`

启动后台监控任务；若已运行会返回 `status=info`。

**请求体**：无

**响应示例**

```json
{
  "status": "success",
  "message": "Monitoring service started"
}
```

### `POST /alert/stop-monitoring`

停止监控循环并保留已有卡片数据。

**响应示例**

```json
{
  "status": "success",
  "message": "Monitoring service stopped"
}
```

### `GET /alert/monitoring-status`

返回监控开关、阈值、上次告警时间以及卡片统计。

**响应字段**

- `status`：`running` / `stopped`
- `trigger_threshold` / `resolve_threshold`
- `interval`：监控周期（秒）
- `last_alerts`：各 LP 最近一次触发时间（ISO8601）
- `cards.total`：卡片总数
- `cards.by_status`：按状态统计

### `GET /alert/cards`

列出告警卡片，支持 `status` 和 `lp` 过滤。

**查询参数**

- `status`（可选）：`awaiting_hitl`、`ignored`、`completed` 等
- `lp`（可选）：LP 名称

**响应示例**

```json
{
  "cards": [
    {
      "id": "b946...",
      "lp": "[CFH] MAJESTIC FIN TRADE",
      "status": "awaiting_hitl",
      "margin_level": 92.5,
      "created_at": "2024-05-20T03:12:45Z",
      "ignore_until": null,
      "last_notified_at": "2024-05-20T03:15:45Z",
      "notifications_sent": 3,
      "threshold": 90.0,
      "hysteresis_threshold": 85.0,
      "last_margin_snapshot": {"Margin Utilization %": 92.5, ...}
    }
  ]
}
```

### `GET /alert/cards/{card_id}`

查看卡片详情，包括完整 `history`（系统/人工操作）、`reports`（初次与复查结果）。

**响应关键字段**

- `reports`：每次调用 margin 接口时返回的原始响应
- `history`：操作时间线，含 `actor`、`action`、`message`、`metadata`

### `POST /alert/cards/{card_id}/hitl`

记录人工审核意见并触发 `/agent/margin-check/recheck`。

**请求示例**

```json
{
  "decision": "reduce-position",
  "notes": "建议减仓 20%，请复查"
}
```

**响应**：返回最新的卡片状态；若缺少 `thread_id`，系统会在 history 中记录并要求人工重新生成报告。

### `POST /alert/cards/{card_id}/ignore`

在指定时间内静默告警，可通过 `duration_minutes` 或 `ignore_until` 提供忽略周期。

**请求示例**

```json
{
  "duration_minutes": 60
}
```

或

```json
{
  "ignore_until": "2024-05-20T10:00:00Z"
}
```

**响应**：返回更新后的卡片信息，状态将变为 `ignored`，并记录历史事件。

### `POST /alert/cards/{card_id}/override`

人工强制修改卡片状态（如 `completed`、`awaiting_hitl`、`overridden`）。常用于紧急干预或手动关闭。

**请求示例**

```json
{
  "status": "completed",
  "reason": "已通过其他渠道处理"
}
```

### `POST /alert/test-alert`

用于调试，直接输出日志中警告信息，不会创建卡片。

**查询参数**

- `lp_name`（默认 `TEST_LP`）
- `margin_level`（默认 `85.0`）

## 与主服务的集成

- 触发时向 `MARGIN_CHECK_URL` 发送 `eventType=MARGIN_ALERT` 和 LP 数据，保存返回的 `thread_id` 及报告内容。
- 人工反馈后，再向 `MARGIN_RECHECK_URL` 发送 `thread_id`，根据最新 `margin` 自动判断是否解除。

## 注意事项

- 告警卡片数据存储于内存，重启服务会丢失现有状态；如需持久化可接入数据库。
- 忽略状态到期后若阈值仍超标，系统会自动恢复提醒并重置通知节奏。
- 所有接口返回的时间戳均为 UTC（ISO8601）。
