"""
重构后的待办事项管理应用

这是一个经过重构的待办事项管理器应用，具有以下改进：
- 完整的函数文档字符串
- 更清晰的变量命名
- 更好的代码组织和可读性
- 类型提示的完整使用

功能：
- 创建和管理待办事项
- 标记任务完成状态
- 查看所有任务或仅查看未完成任务
"""

from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TodoItem:
    """
    待办事项数据类
    
    属性:
        title (str): 待办事项的标题
        description (str): 待办事项的详细描述，默认为空字符串
        completed (bool): 完成状态，默认为 False
        created_at (datetime): 创建时间，默认为当前时间
    """
    
    title: str
    description: str = ""
    completed: bool = False
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """初始化后处理：如果未指定创建时间，则设置为当前时间"""
        if self.created_at is None:
            self.created_at = datetime.now()


class TodoManager:
    """
    待办事项管理器类
    
    提供待办事项的创建、管理、查询和状态更新功能。
    """

    def __init__(self) -> None:
        """
        初始化待办事项管理器
        
        创建一个新的待办事项列表，初始为空
        """
        self.todo_list: List[TodoItem] = []

    def add_todo_item(self, title: str, description: str = "") -> TodoItem:
        """
        添加新的待办事项
        
        Args:
            title (str): 待办事项的标题，必填项
            description (str): 待办事项的详细描述，可选，默认为空字符串
            
        Returns:
            TodoItem: 新创建的待办事项对象
            
        Raises:
            ValueError: 当标题为空字符串时抛出异常
        """
        if not title.strip():
            raise ValueError("待办事项标题不能为空")
            
        new_todo = TodoItem(title=title, description=description)
        self.todo_list.append(new_todo)
        return new_todo

    def mark_todo_as_completed(self, title: str) -> bool:
        """
        根据标题标记待办事项为已完成状态
        
        Args:
            title (str): 要标记为完成的待办事项标题
            
        Returns:
            bool: 如果找到并成功标记返回 True，否则返回 False
        """
        for todo_item in self.todo_list:
            if todo_item.title == title:
                todo_item.completed = True
                return True
        return False

    def get_all_todos(self) -> List[TodoItem]:
        """
        获取所有待办事项的副本
        
        Returns:
            List[TodoItem]: 包含所有待办事项的列表（副本）
        """
        return self.todo_list.copy()

    def get_pending_todos(self) -> List[TodoItem]:
        """
        获取所有未完成的待办事项
        
        Returns:
            List[TodoItem]: 包含所有未完成待办事项的列表
        """
        return [todo for todo in self.todo_list if not todo.completed]

    def get_completed_todos(self) -> List[TodoItem]:
        """
        获取所有已完成的待办事项
        
        Returns:
            List[TodoItem]: 包含所有已完成待办事项的列表
        """
        return [todo for todo in self.todo_list if todo.completed]

    def get_todo_count(self) -> dict:
        """
        获取待办事项统计信息
        
        Returns:
            dict: 包含总数量、已完成数量和未完成数量的字典
        """
        total_count = len(self.todo_list)
        completed_count = len(self.get_completed_todos())
        pending_count = len(self.get_pending_todos())
        
        return {
            "total": total_count,
            "completed": completed_count,
            "pending": pending_count
        }


def display_todos(todo_items: List[TodoItem], title: str = "待办事项") -> None:
    """
    显示待办事项列表
    
    Args:
        todo_items (List[TodoItem]): 要显示的待办事项列表
        title (str): 列表的标题，默认为"待办事项"
    """
    print(f"\n{title}:")
    if not todo_items:
        print("  暂无待办事项")
        return
        
    for todo in todo_items:
        status_icon = "[x]" if todo.completed else "[ ]"
        print(f"  {status_icon} {todo.title}")
        if todo.description:
            print(f"      {todo.description}")


def display_todo_statistics(manager: TodoManager) -> None:
    """
    显示待办事项统计信息
    
    Args:
        manager (TodoManager): 待办事项管理器实例
    """
    stats = manager.get_todo_count()
    print(f"\n统计信息:")
    print(f"  总计: {stats['total']}")
    print(f"  已完成: {stats['completed']}")
    print(f"  未完成: {stats['pending']}")


def main() -> None:
    """
    主函数 - 演示待办事项管理器的使用
    
    创建管理器实例，添加示例待办事项，
    演示各种操作并显示结果。
    """
    # 创建待办事项管理器实例
    todo_manager = TodoManager()

    # 添加示例待办事项
    try:
        todo_manager.add_todo_item("学习 ReAct Agent", "理解思考-行动-观察循环")
        todo_manager.add_todo_item("实现 CodeMate", "基于 GLM 的代码分析助手")
        todo_manager.add_todo_item("重构示例项目", "添加完整文档和改进代码质量")
        print("✓ 成功添加示例待办事项")
    except ValueError as error:
        print(f"✗ 添加待办事项失败: {error}")

    # 显示所有待办事项
    display_todos(todo_manager.get_all_todos(), "所有待办事项")

    # 显示未完成的待办事项
    display_todos(todo_manager.get_pending_todos(), "未完成待办事项")

    # 完成一个任务
    task_to_complete = "学习 ReAct Agent"
    if todo_manager.mark_todo_as_completed(task_to_complete):
        print(f"\n✓ 已完成任务: {task_to_complete}")
    else:
        print(f"\n✗ 未找到任务: {task_to_complete}")

    # 显示更新后的待办事项列表
    display_todos(todo_manager.get_all_todos(), "更新后的待办事项")

    # 显示统计信息
    display_todo_statistics(todo_manager)

    # 演示错误处理
    print("\n演示错误处理:")
    try:
        todo_manager.add_todo_item("")  # 尝试添加空标题
    except ValueError as error:
        print(f"✓ 正确捕获错误: {error}")


if __name__ == "__main__":
    main()