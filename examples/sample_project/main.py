"""
示例项目 - 简单的待办事项应用

这是一个用于测试 Oh-My-Claw 的示例项目。
"""

from typing import List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Todo:
    """待办事项"""
    title: str
    description: str = ""
    completed: bool = False
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class TodoManager:
    """待办事项管理器"""

    def __init__(self):
        self.todos: List[Todo] = []

    def add(self, title: str, description: str = "") -> Todo:
        """添加新的待办事项"""
        todo = Todo(title=title, description=description)
        self.todos.append(todo)
        return todo

    def complete(self, title: str) -> bool:
        """标记待办事项为完成"""
        for todo in self.todos:
            if todo.title == title:
                todo.completed = True
                return True
        return False

    def list_all(self) -> List[Todo]:
        """列出所有待办事项"""
        return self.todos.copy()

    def list_pending(self) -> List[Todo]:
        """列出未完成的待办事项"""
        return [t for t in self.todos if not t.completed]


def main():
    """主函数"""
    manager = TodoManager()

    # 添加示例待办事项
    manager.add("学习 ReAct Agent", "理解思考-行动-观察循环")
    manager.add("实现 Oh-My-Claw", "基于 GLM 的代码分析助手")

    # 列出待办事项
    print("待办事项列表:")
    for todo in manager.list_pending():
        print(f"  [ ] {todo.title}")

    # 完成一个任务
    manager.complete("学习 ReAct Agent")
    print("\n更新后:")
    for todo in manager.list_all():
        status = "[x]" if todo.completed else "[ ]"
        print(f"  {status} {todo.title}")


if __name__ == "__main__":
    main()
