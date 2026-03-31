"""
Oh-My-Claw CLI

命令行交互入口。
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.text import Text
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style

from codemate_agent.config import Config, get_config
from codemate_agent.llm.client import LLMClient
from codemate_agent.agent import CodeMateAgent
from codemate_agent.tools import get_all_tools
from codemate_agent.logging import setup_logger, TraceLogger, SessionMetrics, generate_session_id, TraceEventType
from codemate_agent.persistence import SessionStorage, MemoryManager, SessionIndex
from codemate_agent.context import CompressionConfig
from codemate_agent.ui import console, print_banner, print_help, print_startup_summary, ProgressDisplay
from codemate_agent.commands import handle_command


def _print_cli_error(prefix: str, detail: object) -> None:
    """安全打印错误，避免 Rich 将错误文本中的方括号当作 markup 解析。"""
    console.print(f"{prefix}: {detail}", style="red", markup=False)


def _plain_panel(content: object, *, title: str, border_style: str) -> Panel:
    """使用纯文本 renderable 构造 Panel，避免 Rich 解析动态 markup。"""
    return Panel(Text(str(content or "")), title=title, border_style=border_style)


def _strip_hidden_reasoning(text: str) -> str:
    """移除泄露到最终回答中的 think 块和 MiniMax 工具协议残片。"""
    cleaned = text or ""
    cleanup_patterns = (
        r"<think>.*?</think>",
        r"<minimax:tool_call>.*?</minimax:tool_call>",
        r"<invoke\b[^>]*>.*?</invoke>",
        r"</?(?:parameter|minimax:tool_call|invoke)\b[^>]*>",
        r"\[tool_call\].*?\[/tool_call\]",
        r"\[invoke\b[^\]]*\].*?\[/invoke\]",
        r"\[/?(?:tool_call|invoke|parameter)\b[^\]]*\]",
    )
    for pattern in cleanup_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL | re.IGNORECASE)

    lines = []
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        if line.startswith(("@@", "---", "+++", "[PATH]")):
            continue
        if any(token in line.lower() for token in (
            "<parameter",
            "</parameter>",
            "</invoke>",
            "[parameter",
            "[/parameter]",
            "[invoke",
            "[/invoke]",
            "[tool_call]",
            "[/tool_call]",
        )):
            continue
        lines.append(raw_line)

    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned, flags=re.DOTALL).strip()
    return cleaned or (text or "").strip()


def _find_existing_artifacts(text: str, cwd: Path) -> list[Path]:
    """从回答中提取并验证存在的产物路径。"""
    normalized_text = text or ""
    artifact_context_markers = (
        "已生成",
        "已创建",
        "已写入",
        "created",
        "generated",
        "written to",
        "输出到",
    )
    if not any(marker.lower() in normalized_text.lower() for marker in artifact_context_markers):
        return []

    candidates: set[str] = set()

    artifact_line_patterns = (
        r"(?:已生成|已创建|已写入|输出到)\S*[:：]?\s*`([^`\n]+)`",
        r"(?:created|generated|written to)\s+`([^`\n]+)`",
        r"(?:已生成|已创建|已写入|输出到)\S*[:：]?\s*((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+)",
        r"(?:created|generated|written to)\s+((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+)",
    )

    for pattern in artifact_line_patterns:
        for match in re.findall(pattern, normalized_text, flags=re.IGNORECASE):
            candidates.add(match.strip())

    for match in re.findall(r"`([^`\n]+)`", normalized_text):
        candidates.add(match.strip())

    resolved: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        raw = Path(candidate)
        path = raw if raw.is_absolute() else cwd / raw
        try:
            normalized = path.resolve()
        except OSError:
            continue
        if normalized.exists() and normalized.is_file() and normalized not in seen:
            seen.add(normalized)
            resolved.append(normalized)
    return resolved


def _show_artifact_summary(result: str, cwd: Path) -> None:
    """显示回答中提及且实际存在的产物文件。"""
    artifacts = _find_existing_artifacts(result, cwd)
    if not artifacts:
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("产物", style="cyan")
    table.add_column("大小", justify="right")

    for artifact in artifacts:
        try:
            rel = artifact.relative_to(cwd)
            label = str(rel)
        except ValueError:
            label = str(artifact)
        table.add_row(label, f"{artifact.stat().st_size} bytes")

    console.print(Panel(table, title="[bold]已验证产物[/bold]", border_style="cyan"))


def _classify_shell_risk(command: str) -> str:
    """粗粒度 shell 风险分类，用于确认提示。"""
    text = (command or "").lower()
    high_risk_markers = (
        " rm ", " rm-", " chmod ", " chown ", " dd ", " mkfs ", " sudo ", ">/", ">>",
        " curl ", " wget ", "| sh", "| bash",
    )
    padded = f" {text} "
    if any(marker in padded for marker in high_risk_markers):
        return "high"
    return "normal"


def _canonical_confirm_response(response: str) -> str:
    """规范化确认输入，容忍重复按键（如 yyyyy）。"""
    clean = (response or "").strip().lower()
    aliases = {"yes": "y", "all": "a", "no": "n", "quit": "q"}
    if clean in aliases:
        return aliases[clean]
    if clean in {"y", "a", "n", "q"}:
        return clean
    if clean and len(set(clean)) == 1 and clean[0] in {"y", "a", "n", "q"}:
        return clean[0]
    return clean


def _should_auto_confirm(batch_state: dict, tool_name: str) -> bool:
    _ = tool_name
    return bool(batch_state.get("auto_confirm"))


def run_interactive(config: Config) -> None:
    """运行交互模式"""
    print_banner()

    # 设置日志级别
    setup_logger("codemate", level=config.log_level)

    # 显示配置信息
    config.cwd = Path.cwd()
    print_startup_summary(config)
    console.print("")

    # 初始化日志系统
    session_id = generate_session_id()
    trace_logger = TraceLogger(
        session_id=session_id,
        trace_dir=config.trace_dir,
        enabled=config.trace_enabled,
    ) if config.trace_enabled else None

    metrics = SessionMetrics(
        session_id=session_id,
        model=config.model,
    ) if config.metrics_enabled else None

    # 初始化持久化系统
    session_storage = None
    memory_manager = None
    session_index = None

    if config.persistence_enabled:
        session_storage = SessionStorage(
            sessions_dir=config.sessions_dir,
            session_id=session_id,
        )
        session_storage.ensure_dir()
        session_storage.update_metadata(title="新会话")

        memory_manager = MemoryManager(memory_dir=config.memory_dir)
        session_index = SessionIndex(sessions_dir=config.sessions_dir)

    # 定义计划显示回调函数（需要在 try 块之前定义）
    def plan_display_callback(plan_text: str) -> None:
        """
        显示执行计划

        Args:
            plan_text: TodoWrite 返回的计划文本
        """
        console.print(f"\n[cyan]▶ 生成执行计划[/cyan]")
        console.print(Panel(Text(plan_text), border_style="cyan", padding=(0, 1)))
        console.print("")  # 空行

    # 创建进度显示实例
    progress_display = ProgressDisplay(console)

    # 初始化 Agent
    try:
        llm = LLMClient(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            temperature=config.temperature,
            provider=config.api_provider,
        )
        tools = get_all_tools()

        # 创建压缩配置
        compression_config = CompressionConfig.from_env() if config.persistence_enabled else None

        agent = CodeMateAgent(
            llm_client=llm,
            tools=tools,
            max_rounds=config.max_rounds,
            trace_logger=trace_logger,
            metrics=metrics,
            session_storage=session_storage,
            memory_manager=memory_manager,
            compression_enabled=config.persistence_enabled,
            compression_config=compression_config,
            planning_enabled=config.persistence_enabled,
            plan_display_callback=plan_display_callback,
            progress_callback=progress_display.on_event,
            repo_rag_enabled=config.repo_rag_enabled,
            repo_rag_top_k=config.repo_rag_top_k,
            repo_rag_char_budget=config.repo_rag_char_budget,
        )
    except Exception as e:
        _print_cli_error("初始化失败", e)
        console.print("\n[yellow]提示: 请确保已设置 API_KEY 环境变量或在 .env 文件中配置[/yellow]")
        sys.exit(1)

    # 历史记录和样式
    history_path = Path(config.config_dir) / "history"

    # 定义 prompt_toolkit 样式
    prompt_style = Style.from_dict({
        'prompt': 'ansicyan bold',
    })

    session = PromptSession(
        history=FileHistory(str(history_path)),
        style=prompt_style,
    )

    # 定义用户确认回调函数（支持批量确认）
    # 使用闭包保存批量确认状态
    batch_state = {"auto_confirm": False, "auto_cancel": False}

    def confirm_callback(tool_name: str, arguments: dict) -> bool:
        """
        危险操作的确认回调（支持批量确认）

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            bool: 用户是否同意执行
        """
        # 检查批量确认状态
        if _should_auto_confirm(batch_state, tool_name):
            return True
        if batch_state["auto_cancel"]:
            return False

        # 格式化参数显示 - 根据工具类型优化
        if tool_name == "write_file":
            file_path = arguments.get("file_path", "未知文件")
            content = arguments.get("content", "")
            content_preview = f"({len(content)} 字符)" if content else "(空)"
            params_display = f"file_path={repr(file_path)}, content={content_preview}"
        elif tool_name == "delete_file":
            file_path = arguments.get("file_path", "未知文件")
            params_display = f"file_path={repr(file_path)}"
        elif tool_name in {"run_shell", "background_run"}:
            cmd = arguments.get("command", "")
            cmd_preview = (cmd[:60] + "...") if len(cmd) > 60 else cmd
            risk_level = _classify_shell_risk(cmd)
            risk_label = "高风险" if risk_level == "high" else "常规"
            params_display = f"command={repr(cmd_preview)} (风险等级: {risk_label})"
        else:
            # 通用格式化，限制每个参数的显示长度
            params = []
            for k, v in arguments.items():
                v_str = repr(v)
                if len(v_str) > 50:
                    v_str = v_str[:47] + "..."
                params.append(f"{k}={v_str}")
            params_display = ", ".join(params)

        # 显示确认提示
        console.print(f"\n[red]⚠️  即将执行危险操作:[/red]")
        console.print(f"  [yellow]工具:[/yellow] {tool_name}")
        console.print(f"  [yellow]参数:[/yellow] {params_display}")

        # 获取用户输入
        while True:
            try:
                response = _canonical_confirm_response(session.prompt("  确认执行吗？(y/a/n/q): "))
                if response == "y":
                    console.print("[green]✓[/green] 已同意执行\n")
                    return True
                elif response == "a":
                    console.print("[green]✓[/green] 已同意执行（后续操作自动确认）\n")
                    batch_state["auto_confirm"] = True
                    return True
                elif response in {"n", ""}:
                    console.print("[red]✗[/red] 已取消操作\n")
                    return False
                elif response == "q":
                    console.print("[red]✗[/red] 已取消操作（后续操作自动取消）\n")
                    batch_state["auto_cancel"] = True
                    return False
            except (KeyboardInterrupt, EOFError):
                console.print("\n[red]✗[/red] 已取消操作\n")
                return False

    # 重新初始化 Agent，传入确认回调
    agent.confirm_callback = confirm_callback

    console.print("[green]✓[/green] Agent 已就绪，来聊天吧～（输入 'exit' 或 'quit' 退出）\n")

    while True:
        try:
            user_input = session.prompt(
                '🐱 You > ',
                auto_suggest=AutoSuggestFromHistory()
            ).strip()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit", "q"]:
                console.print("\n[yellow]再见！[/yellow]")
                # 结束日志
                if trace_logger:
                    trace_logger.finalize()
                if metrics:
                    metrics.finalize()
                    metrics.print_summary()
                    metrics.save(config.metrics_dir)
                break

            # 处理特殊命令
            if user_input.startswith("/"):
                handle_command(user_input, agent, session_index, session_storage, memory_manager, config.sessions_dir)
                continue

            # 运行 Agent
            console.print("\n[bold yellow]🐾 Oh-My-Claw:[/bold yellow] [dim]思考中...[/dim]\n")

            try:
                result = agent.run(user_input)
                display_result = _strip_hidden_reasoning(result)

                # 显示结果
                console.print(_plain_panel(display_result, title="[bold green]答案[/bold green]", border_style="green"))
                _show_artifact_summary(display_result, Path.cwd())

                # 显示统计
                stats = agent.get_stats()
                console.print(f"\n[dim]━━━ 轮数: {stats['round_count']} | Tokens: {stats['total_tokens']} ━━━[/dim]\n")

                # 每次对话结束后更新 trace
                if trace_logger:
                    trace_logger.finalize()

            except Exception as e:
                _print_cli_error("执行出错", e)
                console.print("")
                if trace_logger:
                    trace_logger.log_event(
                        TraceEventType.ERROR,
                        {"error": str(e), "type": type(e).__name__},
                    )

        except KeyboardInterrupt:
            console.print("\n\n[yellow]中断[/yellow]")
            continue
        except EOFError:
            console.print("\n\n[yellow]再见！[/yellow]")
            # 结束日志
            if trace_logger:
                trace_logger.finalize()
            if metrics:
                metrics.finalize()
                metrics.print_summary()
                metrics.save(config.metrics_dir)
            break


def run_single_prompt(prompt: str, config: Config) -> None:
    """运行单次查询模式"""
    # 设置日志级别
    setup_logger("codemate", level=config.log_level)

    # 初始化日志系统
    session_id = generate_session_id()
    trace_logger = TraceLogger(
        session_id=session_id,
        trace_dir=config.trace_dir,
        enabled=config.trace_enabled,
    ) if config.trace_enabled else None

    metrics = SessionMetrics(
        session_id=session_id,
        model=config.model,
    ) if config.metrics_enabled else None

    # 初始化持久化系统
    session_storage = None
    memory_manager = None
    session_index = None

    if config.persistence_enabled:
        session_storage = SessionStorage(
            sessions_dir=config.sessions_dir,
            session_id=session_id,
        )
        session_storage.ensure_dir()
        session_storage.update_metadata(title=prompt[:50])

        memory_manager = MemoryManager(memory_dir=config.memory_dir)
        session_index = SessionIndex(sessions_dir=config.sessions_dir)

    # 定义计划显示回调函数（单次模式使用简单的 console.print）
    def plan_display_callback(plan_text: str) -> None:
        console.print(f"\n[cyan]▶ 生成执行计划[/cyan]")
        console.print(Panel(Text(plan_text), border_style="cyan", padding=(0, 1)))
        console.print("")

    # 创建进度显示实例（单次模式也启用进度显示）
    progress_display = ProgressDisplay(console)

    # 初始化 Agent
    try:
        llm = LLMClient(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            temperature=config.temperature,
            provider=config.api_provider,
        )
        tools = get_all_tools()

        # 创建压缩配置
        compression_config = CompressionConfig.from_env() if config.persistence_enabled else None

        agent = CodeMateAgent(
            llm_client=llm,
            tools=tools,
            max_rounds=config.max_rounds,
            trace_logger=trace_logger,
            metrics=metrics,
            session_storage=session_storage,
            memory_manager=memory_manager,
            compression_enabled=config.persistence_enabled,
            compression_config=compression_config,
            planning_enabled=config.persistence_enabled,
            plan_display_callback=plan_display_callback,
            progress_callback=progress_display.on_event,
        )
    except Exception as e:
        _print_cli_error("初始化失败", e)
        sys.exit(1)

    console.print(f"[cyan]问题:[/cyan] {prompt}\n")
    console.print("[bold yellow]Agent:[/bold yellow] [dim]思考中...[/dim]\n")

    try:
        result = agent.run(prompt)
        display_result = _strip_hidden_reasoning(result)
        console.print(_plain_panel(display_result, title="[bold green]答案[/bold green]", border_style="green"))
        _show_artifact_summary(display_result, Path.cwd())

        stats = agent.get_stats()
        console.print(f"\n[dim]轮数: {stats['round_count']} | Tokens: {stats['total_tokens']}[/dim]")

        # 更新会话索引
        if session_storage and session_index:
            metadata = session_storage.get_metadata()
            if metadata:
                session_index.update(metadata)

        # 结束日志并显示统计
        if trace_logger:
            trace_logger.finalize()
        if metrics:
            metrics.finalize()
            metrics.print_summary()
            metrics.save(config.metrics_dir)

    except Exception as e:
        _print_cli_error("执行出错", e)
        if trace_logger:
            trace_logger.log_event(
                TraceEventType.ERROR,
                {"error": str(e), "type": type(e).__name__},
            )


def main() -> None:
    """主入口"""
    parser = argparse.ArgumentParser(
        description="Oh-My-Claw - 基于 Function Calling 的工程执行型代码助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  ohmyclaw                    # 交互模式（推荐）
  ohmyclaw "分析这个项目"     # 单次查询
  codemate --model MiniMax-M2 # 兼容旧命令
        """
    )

    parser.add_argument(
        "prompt",
        nargs="?",
        help="单次查询的问题（不指定则进入交互模式）"
    )
    parser.add_argument(
        "--model", "-m",
        help="使用的模型 (默认: MiniMax-M2)"
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        help="最大对话轮数 (默认: 50)"
    )
    parser.add_argument(
        "--api-key",
        help="API Key"
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="oh-my-claw 0.3.0"
    )

    args = parser.parse_args()

    # 加载配置
    config = Config.from_env()

    # 命令行参数覆盖
    if args.model:
        config.model = args.model
    if args.max_rounds:
        config.max_rounds = args.max_rounds
    if args.api_key:
        config.api_key = args.api_key

    # 验证配置
    valid, error = config.validate()
    if not valid:
        _print_cli_error("配置错误", error)
        sys.exit(1)

    # 运行
    if args.prompt:
        run_single_prompt(args.prompt, config)
    else:
        run_interactive(config)


if __name__ == "__main__":
    main()
