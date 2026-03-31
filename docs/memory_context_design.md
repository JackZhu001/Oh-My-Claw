# CodeMate 记忆系统与上下文工程设计（2026-03-31）

本文档描述 CodeMate 在长任务场景下如何管理上下文、记忆与检索，保证执行稳定性与可恢复性。

## 1. 设计目标

1. 在长链路任务中保持任务主线不丢失
2. 上下文逼近上限时平滑降载，避免硬截断
3. 关键事实可回溯、可验证、可跨会话复用
4. 用户可手动干预压缩与检索行为

## 2. 记忆分层模型

## 2.1 短时记忆（Short-term）

- 载体：当前 `messages`
- 内容：用户消息、assistant 消息、tool 结果
- 作用：支撑当前轮决策

风险：体量增长最快，最易触发 token 压力。

## 2.2 工作记忆（Working memory）

- 载体：todo 状态、阶段信息、关键运行时提示
- 作用：在多轮过程中保持“当前做到了哪一步”

建议：

- 里程碑与阻塞项使用结构化文本表示
- 每次阶段迁移后显式更新状态

## 2.3 长时记忆（Long-term）

- 载体：持久化会话、摘要、项目记忆文件
- 能力：跨会话复用事实与决策上下文

## 2.4 RepoRAG（检索记忆层）

RepoRAG 不替代压缩，而是补充“首轮相关事实注入”。

当前召回源：

- 持久记忆文档（memory）
- 仓库根目录 markdown
- `docs/**/*.md`
- 代码文件切块（可配置开关）

关键能力：

- BM25 query-aware 排序
- source 限流（每来源片段上限）
- 字符预算裁剪
- 代码/文档双通道召回

## 3. 压缩体系（Context Compressor）

## 3.1 Micro Compact（每轮）

目标：优先控制旧工具输出体积。

策略：

- 默认保留最近若干轮工具输出
- 更早输出进行 Soft Trim / Hard Clear
- 可按工具白名单/黑名单调整

## 3.2 Auto Compact（阈值触发）

触发后动作：

1. 写 transcript（保留完整历史）
2. 摘要化旧轮次，保留关键最近轮
3. 将压缩结果回注会话

## 3.3 Manual Compact（`/compact`）

用户主动触发压缩，常用于：

- 切换任务阶段前
- 进入大文件修改前
- 发现上下文明显膨胀时

## 4. 工具输出截断策略

目标：减少低价值 token 占用，同时保留可执行信号。

典型策略：

- `run_shell`：偏向保留尾部（错误通常在尾部）
- `search_*`：采样与摘要保留
- `read_file`：首尾保留并限制体积

## 5. Team 模式与上下文联动

TeamRuntime 会把以下信息注入上下文：

- inbox 消息摘要（`<team_update>`）
- 后台任务结果摘要（`<background_results>`）
- 身份块（`<identity>`，用于防角色漂移）

这保证了多角色协作时状态连续性。

## 6. 关键配置项

### 6.1 压缩相关

- `CONTEXT_WINDOW`
- `COMPRESSION_THRESHOLD`
- `TOKEN_THRESHOLD`
- `MICRO_COMPACT_KEEP`
- `MICRO_SOFT_TRIM_RATIO`
- `MICRO_HARD_CLEAR_RATIO`
- `MICRO_HARD_CLEAR_MIN_CHARS`

### 6.2 RepoRAG 相关

- `REPO_RAG_ENABLED`
- `REPO_RAG_TOP_K`
- `REPO_RAG_CHAR_BUDGET`
- `REPO_RAG_CODE_ENABLED`
- `REPO_RAG_CODE_ROOTS`
- `REPO_RAG_CODE_EXTENSIONS`
- `REPO_RAG_CODE_MAX_FILES`
- `REPO_RAG_CODE_MAX_FILE_BYTES`

### 6.3 观测相关

- `HEARTBEAT_ENABLED`
- `HEARTBEAT_TIMEOUT_SECONDS`
- `HEARTBEAT_POLL_SECONDS`

## 7. 常见问题与建议

## 7.1 症状：长任务后回答变空泛

可能原因：

- RepoRAG 未命中关键文档
- 压缩过于激进
- 工具输出被噪声占满

建议：

1. 提高 `REPO_RAG_TOP_K`
2. 调整 `MICRO_COMPACT_KEEP`
3. 使用 `/rag` 检查召回内容是否对题

## 7.2 症状：频繁触发超时告警

可能原因：

- 查询范围过大
- 代码召回文件数过多
- 上游模型波动

建议：

1. 降低 `REPO_RAG_CODE_MAX_FILES`
2. 增大 `HEARTBEAT_TIMEOUT_SECONDS`
3. 对复杂任务拆阶段执行

## 8. 后续优化方向

1. RepoRAG 增量索引缓存（避免每轮全量重建）
2. 工作记忆结构化 schema（里程碑/阻塞/下一步）
3. 产物验收信号与记忆系统打通（自动写入可复核事实）

---

结论：CodeMate 的记忆与上下文工程已具备长任务可用性，下一阶段应重点优化检索性能与验收真实性闭环。
