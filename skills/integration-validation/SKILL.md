---
name: integration-validation
description: |
  端到端集成验收 Runbook。用于一次性验证 task-system、background-tasks、team 事件链路，
  强制按返回值驱动（避免硬编码 task_id），并包含重复 background_run 去重与顺序护栏检查。
trigger_priority: 1
trigger_min_hits: 1
trigger_keywords:
  - 集成演练
  - 集成验证
  - 集成验收
  - 端到端验证
  - 端到端验收
  - integration test
  - integration validation
  - e2e validation
  - task-system
  - background-tasks
  - team 验证
  - team integration
---

# Integration Validation Runbook

用于执行稳定、可复现的集成验收，避免“步骤跑偏/ID 错位/证据不闭环”。

## 适用场景

- 用户要求“验证 task-system + background-tasks + team”
- 用户要求“完整验收任务”
- 出现过“重复 background_run、任务 ID 混乱、只凭代码搜索当证据”等问题

## 强制规则（必须遵守）

1. **不要把环境变量字符串当作聊天步骤执行**  
   若用户把 `TEAM_AGENT_ENABLED=true ... python -m ...` 发在对话里，先说明：
   这必须在启动 CLI 前设置，聊天内无效。
2. **所有 task_id 必须来自工具返回值**，禁止写死 `task_id=1/2/...`。
3. **重复 background_run 验证必须使用完全相同的 command 字符串**，且紧随首次调用后立刻执行。
4. **每次 background_run 后必须 check_background**；未 check 前不应再开启新后台任务。
5. **team 验收必须给运行时证据**：`events.jsonl` 片段，不可仅“代码里有该事件”。
6. **联调前先清理测试命名空间**：优先使用 `task_cleanup(namespace="ITEST")`。

## 标准执行流程

> 说明：示例中的 `<id_xxx>` 必须替换为上一步实际返回值。

### A. 建立任务链（task-system）

1. `task_cleanup(namespace="ITEST")`
2. `task_create(subject="ITEST: 实现健康检查API", description="新增 /health endpoint", namespace="ITEST")`
   - 记录返回 `api_task_id`
3. `task_create(subject="ITEST: 补充健康检查测试", description="pytest 覆盖", blocked_by=[api_task_id], namespace="ITEST")`
   - 记录返回 `test_task_id`
4. `task_create(subject="ITEST: 整理发布说明", description="更新变更记录", blocked_by=[test_task_id], namespace="ITEST")`
   - 记录返回 `release_task_id`
5. `task_list(namespace="ITEST")`

### B. 后台任务（background-tasks）

6. `task_update(task_id=api_task_id, status="in_progress", owner="lead")`
7. `background_run(command="bash -lc \"sleep 2 && echo health api done\"", timeout=30)`
   - 记录返回 `bg_task_id`
8. **立刻再次调用同一条命令**：  
   `background_run(command="bash -lc \"sleep 2 && echo health api done\"", timeout=30)`
   - 期望：返回“已存在 running task / 请先 check_background”
9. `check_background(task_id=bg_task_id)` 轮询到非 running

### C. 依赖解除验证

10. `task_update(task_id=api_task_id, status="completed")`
11. `task_get(task_id=test_task_id)`  
    - 验证 `blockedBy` 已不包含 `api_task_id`

### D. Team 注入与证据闭环

12. `run_shell(command="mkdir -p .team/inbox && echo '{\"type\":\"message\",\"from\":\"qa-bot\",\"content\":\"integration ping\",\"timestamp\":1730000000}' >> .team/inbox/lead.jsonl")`
13. `task_list(namespace="ITEST")`（触发下一轮，便于消费 inbox/后台通知）
14. `team_status(event_limit=20)`（输出 team 摘要）
15. `run_shell(command="tail -n 50 .team/events.jsonl")`

## 最终输出模板

输出必须包含 3 段，每段都带“证据”：

1. `task-system`
   - 三个任务的 id/状态
   - `task_get(test_task_id)` 中 blockedBy 的实际值
2. `background-tasks`
   - 首次 `bg_task_id`
   - 第二次调用是否被去重/阻止（原文片段）
   - `check_background` 最终状态
3. `team`
   - `team_status` 的摘要（team/agent/inbox/task_stats）
   - `events.jsonl` 中 `background_results` / `inbox_ingested` 的日志片段

## 失败处理

- 如果 task_create 返回格式异常：先 `task_list()`，按 `subject` 反查 ID 后继续。
- 如果 `.team/events.jsonl` 不存在：明确提示“需以 TEAM_AGENT_ENABLED=true 重启后重试”。
- 若步骤被打断：先恢复变量（task_id/bg_task_id），再继续，不要从头乱重试。
