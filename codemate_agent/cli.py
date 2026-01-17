"""
CodeMate AI CLI

命令行交互入口。
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style

from codemate_agent.config import Config, get_config
from codemate_agent.llm.client import GLMClient
from codemate_agent.agent import CodeMateAgent
from codemate_agent.tools import get_all_tools
from codemate_agent.logging import setup_logger, TraceLogger, SessionMetrics, generate_session_id, TraceEventType
from codemate_agent.persistence import SessionStorage, MemoryManager, SessionIndex
from codemate_agent.context import CompressionConfig

console = Console()


def print_banner() -> None:
    """打印欢迎横幅"""
    banner = r"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ███╗   ██╗███████╗██╗    ██╗      ██╗  ██╗███████╗██╗     ║
║   ████╗  ██║██╔════╝██║    ██║      ██║  ██║██╔════╝██║     ║
║   ██╔██╗ ██║█████╗  ██║ █╗ ██║█████╗███████║█████╗  ██║     ║
║   ██║╚██╗██║██╔══╝  ██║███╗██║╚════╝██╔══██║██╔══╝  ██║     ║
║   ██║ ╚████║███████╗╚███╔███╔╝      ██║  ██║███████╗███████╗║
║   ╚═╝  ╚═══╝╚══════╝ ╚══╝╚══╝       ╚═╝  ╚═╝╚══════╝╚══════╝║
║                                                              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    console.print(banner, style="bold cyan")


class ProgressDisplay:
    """实时进度显示"""

    # 状态图标
    ICONS = {
        "running": "▶",
        "done": "✓",
        "error": "✗",
    }

    def __init__(self, console: Console):
        self.console = console
        self.current_round = 0
        self.current_tool = ""
        self.max_rounds = 50

    def on_event(self, event: str, data: dict) -> None:
        """处理进度事件"""
        if event == "round_start":
            self.current_round = data.get("round", 0)
            self.max_rounds = data.get("max_rounds", 50)
            self._show_round_progress()
        elif event == "tool_call_start":
            self.current_tool = data.get("tool", "")
            args = data.get("args", "")
            self._show_tool_call(self.current_tool, args)
        elif event == "tool_call_end":
            self.current_tool = ""
            # 工具完成，可以显示简单的状态

    def _show_round_progress(self) -> None:
        """显示轮次进度"""
        self.console.print(
            f"[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]\n"
            f"[cyan]  Round {self.current_round}/{self.max_rounds}[/cyan]"
        )

    def _show_tool_call(self, tool: str, args: str) -> None:
        """显示工具调用"""
        if args:
            self.console.print(f"  [dim]└─[/dim] [yellow]{tool}[/yellow] [dim]({args})[/dim]")
        else:
            self.console.print(f"  [dim]└─[/dim] [yellow]{tool}[/yellow]")


def run_interactive(config: Config) -> None:
    """运行交互模式"""
    print_banner()

    # 设置日志级别
    setup_logger("codemate", level=config.log_level)

    # 显示配置信息
    config_table = Table(show_header=False, show_edge=False)
    config_table.add_column("配置项", style="cyan")
    config_table.add_column("值", style="yellow")
    config_table.add_row("模型", config.model)
    config_table.add_row("最大轮数", str(config.max_rounds))
    config_table.add_row("日志级别", config.log_level)
    config_table.add_row("Trace 日志", "启用" if config.trace_enabled else "禁用")
    config_table.add_row("Metrics 统计", "启用" if config.metrics_enabled else "禁用")
    config_table.add_row("对话持久化", "启用" if config.persistence_enabled else "禁用")
    config_table.add_row("上下文压缩", "启用" if config.persistence_enabled else "禁用")  # 与持久化同步
    config_table.add_row("任务规划", "启用" if config.persistence_enabled else "禁用")  # 与持久化同步
    config_table.add_row("工作目录", str(Path.cwd()))
    console.print(Panel(config_table, title="[bold]当前配置[/bold]"))
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
        console.print(Panel(plan_text, border_style="cyan", padding=(0, 1)))
        console.print("")  # 空行

    # 创建进度显示实例
    progress_display = ProgressDisplay(console)

    # 初始化 Agent
    try:
        llm = GLMClient(
            api_key=config.api_key,
            model=config.model,
            temperature=config.temperature,
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
        console.print(f"[red]初始化失败: {e}[/red]")
        console.print("\n[yellow]提示: 请确保已设置 GLM_API_KEY 环境变量或在 .env 文件中配置[/yellow]")
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
        if batch_state["auto_confirm"]:
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
        elif tool_name == "run_shell":
            cmd = arguments.get("command", "")
            cmd_preview = (cmd[:60] + "...") if len(cmd) > 60 else cmd
            params_display = f"command={repr(cmd_preview)}"
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
                response = session.prompt("  确认执行吗？(y/a/n/q): ").strip().lower()
                if response in ['y', 'yes']:
                    console.print("[green]✓[/green] 已同意执行\n")
                    return True
                elif response in ['a', 'all']:
                    console.print("[green]✓[/green] 已同意执行（后续操作自动确认）\n")
                    batch_state["auto_confirm"] = True
                    return True
                elif response in ['n', 'no', '']:
                    console.print("[red]✗[/red] 已取消操作\n")
                    return False
                elif response in ['q', 'quit']:
                    console.print("[red]✗[/red] 已取消操作（后续操作自动取消）\n")
                    batch_state["auto_cancel"] = True
                    return False
            except (KeyboardInterrupt, EOFError):
                console.print("\n[red]✗[/red] 已取消操作\n")
                return False

    # 重新初始化 Agent，传入确认回调
    agent.confirm_callback = confirm_callback

    console.print("[green]✓[/green] Agent 已就绪，输入问题开始对话（输入 'exit' 或 'quit' 退出）\n")

    while True:
        try:
            user_input = session.prompt(
                'You > ',
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
            console.print("\n[bold yellow]Agent:[/bold yellow] [dim]思考中...[/dim]\n")

            try:
                result = agent.run(user_input)

                # 显示结果
                console.print(Panel(result, title="[bold green]答案[/bold green]", border_style="green"))

                # 显示统计
                stats = agent.get_stats()
                console.print(f"\n[dim]━━━ 轮数: {stats['round_count']} | Tokens: {stats['total_tokens']} ━━━[/dim]\n")

                # 每次对话结束后更新 trace
                if trace_logger:
                    trace_logger.finalize()

            except Exception as e:
                console.print(f"[red]执行出错: {e}[/red]\n")
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


def handle_command(
    command: str,
    agent: CodeMateAgent,
    session_index: "SessionIndex | None" = None,
    session_storage: "SessionStorage | None" = None,
    memory_manager: "MemoryManager | None" = None,
    sessions_dir: Path = None,
) -> None:
    """处理斜杠命令"""
    # 解析命令：支持 /history <id> 和 /history<id> 两种格式
    import re

    # 先尝试标准格式（空格分隔）
    parts = command.lower().split(maxsplit=1)
    cmd = parts[0]
    args = parts[1] if len(parts) > 1 else ""

    # 如果没有参数，尝试解析 /history<id> 格式
    if not args and "<" in cmd and ">" in cmd:
        match = re.match(r"(/[a-z]+)<(.+)>", cmd)
        if match:
            cmd = match.group(1)
            args = match.group(2)

    if cmd == "/help":
        print_help()
    elif cmd == "/reset":
        agent.reset()
        console.print("[green]✓[/green] Agent 状态已重置\n")
    elif cmd == "/stats":
        stats = agent.get_stats()
        console.print(f"[cyan]统计信息:[/cyan]\n{stats}\n")
    elif cmd == "/tools":
        tools = agent.tool_registry.list_tools()
        console.print(f"[cyan]可用工具 ({len(tools)}):[/cyan]\n" + "\n".join(f"  - {t}" for t in tools))
    elif cmd == "/sessions":
        _list_sessions(session_index)
    elif cmd == "/history" and args:
        _load_session(args, agent, session_index, sessions_dir)
    elif cmd == "/history":
        console.print("[yellow]用法: /history <会话ID>[/yellow]\n")
    elif cmd == "/memory":
        _show_memory(memory_manager)
    elif cmd == "/save":
        if session_storage:
            _save_session(session_storage, session_index)
        else:
            console.print("[red]对话持久化未启用[/red]\n")
    else:
        console.print(f"[red]未知命令: {command}[/red]")
        console.print("输入 /help 查看可用命令\n")


def print_help() -> None:
    """打印帮助信息"""
    help_text = """
可用命令:

  [cyan]/help[/cyan]       - 显示此帮助信息
  [cyan]/reset[/cyan]      - 重置 Agent 状态
  [cyan]/stats[/cyan]      - 显示统计信息
  [cyan]/tools[/cyan]      - 列出可用工具
  [cyan]/sessions[/cyan]   - 列出历史会话
  [cyan]/history <id>[/cyan] - 加载指定会话
  [cyan]/memory[/cyan]     - 查看长期记忆
  [cyan]/save[/cyan]       - 保存当前会话
  [cyan]exit[/cyan]        - 退出程序

使用技巧:
  - 可以问关于代码结构的问题
  - 可以请求分析特定文件
  - 可以搜索代码中的关键词
  - 按 Tab 键可以自动补全历史输入
  - 使用 /sessions 查看历史对话
"""
    console.print(Panel(help_text, title="[bold]帮助[/bold]", border_style="cyan"))


def _list_sessions(session_index: "SessionIndex | None") -> None:
    """列出历史会话"""
    if session_index is None:
        console.print("[red]会话索引未初始化[/red]\n")
        return

    sessions = session_index.list_recent(limit=10)

    if not sessions:
        console.print("[yellow]暂无历史会话[/yellow]\n")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("会话 ID", style="cyan")
    table.add_column("标题", style="white")
    table.add_column("消息数", justify="right")
    table.add_column("更新时间", style="dim")

    for s in sessions:
        # 截断 session_id 显示
        short_id = s.session_id[:20] + "..."
        table.add_row(short_id, s.title, str(s.message_count), s.updated_at[:19])

    console.print("\n[bold]最近会话:[/bold]")
    console.print(table)
    console.print()


def _load_session(
    session_id: str,
    agent: CodeMateAgent,
    session_index: "SessionIndex | None",
    sessions_dir: Path,
) -> None:
    """加载指定会话"""
    if session_index is None:
        console.print("[red]会话索引未初始化[/red]\n")
        return

    # 查找完整 session_id（支持模糊匹配）
    sessions = session_index.list_all(limit=1000)
    matched = None
    for s in sessions:
        if s.session_id.startswith(session_id):
            matched = s
            break

    if matched is None:
        console.print(f"[red]找不到会话: {session_id}[/red]\n")
        return

    console.print(f"[cyan]正在加载会话: {matched.title}[/cyan]")

    # 从磁盘加载会话
    from codemate_agent.persistence import SessionStorage

    storage = SessionStorage.load(sessions_dir, matched.session_id)
    messages = storage.get_messages_for_agent()

    # 显示摘要（如果有）
    summary = storage.get_summary()
    if summary:
        console.print(Panel(summary[:400] + "..." if len(summary) > 400 else summary,
                          title="[bold]会话摘要[/bold]", border_style="dim"))

    # 加载到 Agent
    agent.load_session(messages)

    console.print(f"[green]✓[/green] 已加载 {len(messages)} 条历史消息\n")


def _show_memory(memory_manager: "MemoryManager | None") -> None:
    """显示长期记忆"""
    if memory_manager is None:
        console.print("[red]记忆管理器未初始化[/red]\n")
        return

    info = memory_manager.get_memory_files_info()

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("记忆文件", style="cyan")
    table.add_column("大小", justify="right")

    for name, data in info.items():
        if data["exists"]:
            size = data["size"]
            table.add_row(name, f"{size} bytes")

    console.print("\n[bold]长期记忆:[/bold]")
    console.print(table)

    # 显示记忆内容摘要
    memory = memory_manager.load_all_memory()
    if memory and not memory.startswith("# 长期记忆\n\n暂无"):
        console.print(Panel(memory[:500] + "..." if len(memory) > 500 else memory,
                          title="[bold]记忆内容[/bold]", border_style="dim"))
    console.print()


def _save_session(
    session_storage: SessionStorage,
    session_index: "SessionIndex | None",
) -> None:
    """保存当前会话"""
    metadata = session_storage.get_metadata()
    if metadata and session_index:
        session_index.update(metadata)
        console.print(f"[green]✓[/green] 会话已保存: {metadata.title}\n")
    else:
        console.print("[green]✓[/green] 会话已保存\n")


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
        console.print(Panel(plan_text, border_style="cyan", padding=(0, 1)))
        console.print("")

    # 创建进度显示实例（单次模式也启用进度显示）
    progress_display = ProgressDisplay(console)

    # 初始化 Agent
    try:
        llm = GLMClient(
            api_key=config.api_key,
            model=config.model,
            temperature=config.temperature,
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
        console.print(f"[red]初始化失败: {e}[/red]")
        sys.exit(1)

    console.print(f"[cyan]问题:[/cyan] {prompt}\n")
    console.print("[bold yellow]Agent:[/bold yellow] [dim]思考中...[/dim]\n")

    try:
        result = agent.run(prompt)
        console.print(Panel(result, title="[bold green]答案[/bold green]", border_style="green"))

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
        console.print(f"[red]执行出错: {e}[/red]")
        if trace_logger:
            trace_logger.log_event(
                TraceEventType.ERROR,
                {"error": str(e), "type": type(e).__name__},
            )


def main() -> None:
    """主入口"""
    parser = argparse.ArgumentParser(
        description="CodeMate AI - 基于 Function Calling 的代码分析 Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  codemate                    # 交互模式
  codemate "分析这个项目"     # 单次查询
  codemate --model glm-4-plus # 使用指定模型
        """
    )

    parser.add_argument(
        "prompt",
        nargs="?",
        help="单次查询的问题（不指定则进入交互模式）"
    )
    parser.add_argument(
        "--model", "-m",
        help="使用的模型 (默认: glm-4-flash)"
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        help="最大对话轮数 (默认: 50)"
    )
    parser.add_argument(
        "--api-key",
        help="GLM API Key"
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="codemate-agent 0.3.0"
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
        console.print(f"[red]配置错误: {error}[/red]")
        sys.exit(1)

    # 运行
    if args.prompt:
        run_single_prompt(args.prompt, config)
    else:
        run_interactive(config)


if __name__ == "__main__":
    main()
