"""
日志系统单元测试
"""

import json
import tempfile
from pathlib import Path
from unittest import TestCase

from codemate_agent.logging import (
    setup_logger,
    TraceLogger,
    SessionMetrics,
    TokenUsage,
    generate_session_id,
    TraceEventType,
)


class TestLogger(TestCase):
    """基础日志测试"""

    def test_setup_logger(self):
        """测试 logger 创建"""
        logger = setup_logger("test", level="DEBUG")
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "test")

    def test_get_logger(self):
        """测试获取 logger"""
        from codemate_agent.logging import get_logger
        logger1 = get_logger("test2")
        logger2 = get_logger("test2")
        # 同名 logger 应该是同一个实例
        self.assertIs(logger1, logger2)


class TestSessionId(TestCase):
    """会话 ID 生成测试"""

    def test_generate_session_id_format(self):
        """测试会话 ID 格式"""
        session_id = generate_session_id()
        # 格式应该是 s-YYYYMMDD-HHMMSS-xxxx
        self.assertTrue(session_id.startswith("s-"))
        parts = session_id.split("-")
        self.assertEqual(len(parts), 4)  # ['s', 'YYYYMMDD', 'HHMMSS', 'xxxx']
        self.assertEqual(len(parts[3]), 4)  # 随机部分是 4 位

    def test_generate_session_id_unique(self):
        """测试会话 ID 唯一性"""
        id1 = generate_session_id()
        id2 = generate_session_id()
        self.assertNotEqual(id1, id2)


class TestTokenUsage(TestCase):
    """Token 使用统计测试"""

    def test_token_usage_init(self):
        """测试 TokenUsage 初始化"""
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        self.assertEqual(usage.input_tokens, 100)
        self.assertEqual(usage.output_tokens, 50)

    def test_token_usage_add(self):
        """测试 TokenUsage 相加"""
        usage1 = TokenUsage(input_tokens=100, output_tokens=50)
        usage2 = TokenUsage(input_tokens=200, output_tokens=100)
        combined = usage1 + usage2
        self.assertEqual(combined.input_tokens, 300)
        self.assertEqual(combined.output_tokens, 150)

    def test_token_usage_from_dict(self):
        """测试从字典创建 TokenUsage"""
        data = {"input_tokens": 100, "output_tokens": 50}
        usage = TokenUsage.from_dict(data)
        self.assertEqual(usage.input_tokens, 100)
        self.assertEqual(usage.output_tokens, 50)

    def test_token_usage_from_dict_alternate_keys(self):
        """测试使用 alternate keys 从字典创建"""
        data = {"prompt_tokens": 100, "completion_tokens": 50}
        usage = TokenUsage.from_dict(data)
        self.assertEqual(usage.input_tokens, 100)
        self.assertEqual(usage.output_tokens, 50)


class TestSessionMetrics(TestCase):
    """会话指标测试"""

    def test_session_metrics_init(self):
        """测试 SessionMetrics 初始化"""
        metrics = SessionMetrics(session_id="test-session")
        self.assertEqual(metrics.session_id, "test-session")
        self.assertEqual(metrics.input_tokens, 0)
        self.assertEqual(metrics.output_tokens, 0)

    def test_record_llm_call(self):
        """测试记录 LLM 调用"""
        metrics = SessionMetrics(session_id="test-session")
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        metrics.record_llm_call(usage)
        self.assertEqual(metrics.input_tokens, 100)
        self.assertEqual(metrics.output_tokens, 50)
        self.assertEqual(metrics.llm_calls, 1)

    def test_record_tool_call(self):
        """测试记录工具调用"""
        metrics = SessionMetrics(session_id="test-session")
        metrics.record_tool_call("read_file", success=True)
        self.assertEqual(metrics.tool_calls.calls.get("read_file"), 1)
        self.assertEqual(metrics.tool_calls.total_calls, 1)

    def test_record_tool_call_error(self):
        """测试记录工具调用失败"""
        metrics = SessionMetrics(session_id="test-session")
        metrics.record_tool_call("read_file", success=False)
        self.assertEqual(metrics.tool_calls.errors.get("read_file"), 1)
        self.assertEqual(metrics.tool_calls.total_errors, 1)

    def test_finalize(self):
        """测试结束会话"""
        metrics = SessionMetrics(session_id="test-session")
        metrics.record_llm_call(TokenUsage(input_tokens=100, output_tokens=50))
        metrics.record_tool_call("read_file")
        stats = metrics.finalize()
        self.assertIsNotNone(stats["end_time"])
        self.assertEqual(stats["tokens"]["input"], 100)
        self.assertEqual(stats["tokens"]["output"], 50)


class TestTraceLogger(TestCase):
    """Trace 日志测试"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.trace_dir = Path(self.temp_dir)

    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_trace_logger_init(self):
        """测试 TraceLogger 初始化"""
        logger = TraceLogger(
            session_id="test-session",
            trace_dir=self.trace_dir,
            enabled=True,
        )
        self.assertEqual(logger.session_id, "test-session")
        self.assertTrue(logger.enabled)

    def test_trace_logger_disabled(self):
        """测试禁用 TraceLogger"""
        logger = TraceLogger(
            session_id="test-session",
            trace_dir=self.trace_dir,
            enabled=False,
        )
        self.assertFalse(logger.enabled)
        # 禁用状态下不应该创建文件
        logger.log_event(TraceEventType.USER_INPUT, {"text": "test"})
        self.assertFalse(logger.jsonl_path.exists())

    def test_trace_logger_log_event(self):
        """测试记录事件"""
        logger = TraceLogger(
            session_id="test-session",
            trace_dir=self.trace_dir,
            enabled=True,
        )
        logger.log_event(TraceEventType.USER_INPUT, {"text": "hello"}, step=1)

        # 检查 JSONL 文件
        self.assertTrue(logger.jsonl_path.exists())
        with open(logger.jsonl_path, "r") as f:
            lines = f.readlines()
            # 第一行是 session_start，第二行是 user_input
            self.assertEqual(len(lines), 2)
            event = json.loads(lines[1])
            self.assertEqual(event["event"], "user_input")
            self.assertEqual(event["step"], 1)
            self.assertEqual(event["payload"]["text"], "hello")

    def test_trace_logger_finalize(self):
        """测试结束日志"""
        logger = TraceLogger(
            session_id="test-session",
            trace_dir=self.trace_dir,
            enabled=True,
        )
        logger.log_event(TraceEventType.USER_INPUT, {"text": "hello"})
        logger.log_event(TraceEventType.LLM_REQUEST, {"model": "glm-4"})

        stats = logger.finalize()

        # 检查统计
        self.assertEqual(stats["llm_calls"], 1)

        # 检查 Markdown 文件
        self.assertTrue(logger.md_path.exists())
        content = logger.md_path.read_text()
        self.assertIn("会话 ID", content)
        self.assertIn("统计摘要", content)

    def test_trace_logger_stats(self):
        """测试统计功能"""
        logger = TraceLogger(
            session_id="test-session",
            trace_dir=self.trace_dir,
            enabled=True,
        )

        # 记录 LLM 调用
        logger.log_event(
            TraceEventType.LLM_REQUEST,
            {"model": "glm-4"},
            step=1,
        )
        logger.log_event(
            TraceEventType.LLM_RESPONSE,
            {"usage": {"input_tokens": 100, "output_tokens": 50}},
            step=1,
        )

        # 记录工具调用
        logger.log_event(
            TraceEventType.TOOL_CALL,
            {"tool": "read_file"},
            step=1,
        )

        stats = logger.get_stats()
        self.assertEqual(stats["llm_calls"], 1)
        self.assertEqual(stats["tool_calls"], 1)
        self.assertEqual(stats["total_input_tokens"], 100)
        self.assertEqual(stats["total_output_tokens"], 50)

    def test_trace_logger_all_event_types(self):
        """测试所有事件类型"""
        logger = TraceLogger(
            session_id="test-session",
            trace_dir=self.trace_dir,
            enabled=True,
        )

        # 测试各种事件类型（不包含 SESSION_START，因为会自动添加）
        events = [
            (TraceEventType.USER_INPUT, {"text": "test"}),
            (TraceEventType.LLM_REQUEST, {"model": "glm-4"}),
            (TraceEventType.LLM_RESPONSE, {"content": "ok"}),
            (TraceEventType.TOOL_CALL, {"tool": "read_file"}),
            (TraceEventType.TOOL_RESULT, {"result": "success"}),
            (TraceEventType.ERROR, {"error": "test error"}),
        ]

        for event_type, payload in events:
            logger.log_event(event_type, payload)

        logger.finalize()

        # 验证 JSONL 文件行数
        # 1 (session_start) + len(events) + 1 (session_end)
        with open(logger.jsonl_path, "r") as f:
            lines = f.readlines()
            self.assertEqual(len(lines), len(events) + 2)


if __name__ == "__main__":
    import unittest
    unittest.main()
