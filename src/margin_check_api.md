# Margin Check API 文档

本文档描述 `src/api/graph.py` 中提供的保证金分析接口，涵盖初始报告、复查以及历史记录查询能力。这些接口通常部署在主服务（默认端口 8000）的 `/agent` 路由下，供告警服务或外部系统调用。

## 通用约定

- **Base URL**：`/agent`
- **Content-Type**：`application/json`
- **返回格式**：成功时返回 JSON；若 `stream=true`，则以 `text/event-stream` 传输 Server-Sent Events（SSE）。
- **语言**：系统默认生成中文报告，可根据传入的 `messages` 控制语言与上下文。

## 数据模型

### EventInput

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `messages` | `[{"role"/"type": str, "content": str}, ...]` | 否 | 用户输入历史，通常为 `role=user` 或 `type=human` 的消息列表。未提供时会使用系统默认提示生成保证金报告。|
| `thread_id` | `string` | 否 | 会话 ID。未提供时服务会根据消息生成一个哈希值。用于后续复查或获取历史。|
| `eventType` | `string` | 否 | 事件类型。当值为 `MARGIN_ALERT` 时表示来自监控告警，接口会跳过意图识别直接产出报告。|
| `payload` | `object` | 否 | 事件负载，仅在 `eventType=MARGIN_ALERT` 时处理。需要包含 `lp`（LP 名称）、`marginLevel`（当前保证金占用，0~1 浮点）、`threshold`（触发阈值，0~1 浮点）。|

### HistoryInput

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `thread_id` | `string` | 是 | 需要查询的会话 ID，对应初次调用或复查响应中的 `thread_id`。|

---

## `POST /agent/margin-check`

执行一次保证金分析流程，并在需要时触发人工审批。支持一次性响应与流式 SSE 两种模式。

### 查询参数

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `stream` | `bool` | `false` | 置为 `true` 时以 SSE 逐步返回模型输出与状态事件。|

### 请求示例

**1. 常规对话请求**
```json
{
  "messages": [
    {"role": "user", "content": "请生成GBE账户的保证金风险报告"}
  ]
}
```

**2. 告警触发请求**（由监控服务调用）
```json
{
  "eventType": "MARGIN_ALERT",
  "payload": {
    "lp": "[CFH] MAJESTIC FIN TRADE",
    "marginLevel": 0.96,
    "threshold": 0.90
  }
}
```

### 非流式响应

- **成功完成**
  ```json
  {
    "type": "complete",
    "status": "completed",
    "content": "...最终生成的保证金分析报告...",
    "thread_id": "margin_check_-123456789"
  }
  ```

- **等待人工审批**（命中 HITL 流程时）
  ```json
  {
    "type": "interrupt",
    "status": "awaiting_approval",
    "interrupt_data": {
      "agent": "human_approval",
      "messages": [...]
    },
    "thread_id": "margin_check_-123456789"
  }
  ```

- **执行异常**
  ```json
  {
    "type": "error",
    "status": "error",
    "error": "具体错误信息",
    "thread_id": "margin_check_-123456789"
  }
  ```

### 流式响应（SSE）

当 `stream=true` 时，接口返回 `text/event-stream`，事件类型如下：

| 事件 | 说明 |
| --- | --- |
| `token` | 模型生成的增量文本，payload 包含 `content` 与 `thread_id`。|
| `interrupt` | 进入人工审批，payload 包含 `status=awaiting_approval` 与 `interrupt_data`。|
| `complete` | 生成流程结束并返回最终文案。|
| `error` | 执行出错时推送错误信息。|
| `end` | 流式响应结束的占位事件。|

调用方需消费完整的 SSE 流，以确保收到最终状态事件。

---

## `POST /agent/margin-check/recheck`

在人类审核反馈后，基于已有会话重新生成实时保证金分析报告。内部会使用默认提示词继续流程。

### 查询参数

与 `/agent/margin-check` 相同，支持 `stream`。

### 请求示例

```json
{
  "thread_id": "margin_check_-123456789"
}
```

- 若缺少 `thread_id`，接口会返回 `400` 错误。

### 响应

结构与初次调用相同：成功时返回 `type=complete`，未通过自动判定时返回 `type=interrupt`，出现异常时返回 `type=error`。SSE 模式下事件类型同上，但 `thread_id` 即为请求中提供的值。

---

## `POST /agent/margin-check/history`

查询指定 `thread_id` 的执行轨迹与节点历史，方便外部系统调试或追踪多轮执行。

### 请求示例

```json
{
  "thread_id": "margin_check_-123456789"
}
```

### 响应字段

```json
{
  "thread_id": "margin_check_-123456789",
  "summary": {
    "total_steps": 8,
    "completed_steps": 6,
    "pending_steps": 2,
    "executed_nodes": ["supervisor", "lp_margin_check_tool"],
    "latest_timestamp": "2024-05-09T12:34:56.123456"
  },
  "execution_history": [
    {
      "checkpoint_id": "...",
      "step": 1,
      "source": "input",
      "writes": {...},
      "created_at": "2024-05-09T12:30:00.000000",
      "values": {
        "messages": [
          {"type": "human", "content": "..."}
        ],
        "intentContext": {...}
      },
      "tasks": [
        {
          "id": "...",
          "name": "supervisor",
          "interrupts": []
        }
      ],
      "executed_nodes": ["supervisor"]
    },
    "...更多步骤..."
  ],
  "status": "success"
}
```

当 `thread_id` 不存在或检查点服务不可用时，接口会返回 `status=error` 并附带错误消息；若请求体缺少 `thread_id`，则返回 `400`。

---

## 错误码与异常处理

| 状态码 | 触发条件 |
| --- | --- |
| `400 Bad Request` | 复查或历史查询缺少必须的 `thread_id`。|
| `500 Internal Server Error` | 图谱执行异常、检查点服务不可用或其他未捕获错误。实际错误信息会在响应 `error` 字段中返回。|

---

## 集成建议

1. **初次告警**：监控服务在达到触发阈值时调用 `/agent/margin-check`，并保存返回的 `thread_id` 以便后续复查。
2. **人工审批**：若返回 `type=interrupt`，由人工工作台根据 `interrupt_data` 做出决策，处理完毕后调用 `/agent/margin-check/recheck`。
3. **历史追溯**：在调试或排查问题时，使用 `/agent/margin-check/history` 查看每一步的执行节点与输出。
4. **流式消费**：需要实时展示报告生成过程时使用 `stream=true`，否则建议使用默认的同步模式以简化集成。
