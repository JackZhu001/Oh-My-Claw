"""
代码分析器模块
"""

import ast
import os
from typing import List
from models import CodeIssue, Severity


class RefactorSuggest:
    """代码重构建议工具"""
    
    def __init__(self):
        self.issues: List[CodeIssue] = []
        self.max_function_length = 50  # 函数最大行数
        self.max_complexity = 10       # 圈复杂度阈值
        self.max_param_count = 5       # 参数数量阈值
        
    def analyze_file(self, file_path: str) -> List[CodeIssue]:
        """
        分析单个 Python 文件
        
        Args:
            file_path: Python 文件路径
            
        Returns:
            List[CodeIssue]: 检测到的问题列表
        """
        self.issues = []
        
        if not os.path.exists(file_path):
            print(f"错误: 文件不存在 - {file_path}")
            return self.issues
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
                
            # 解析 AST
            tree = ast.parse(source_code, filename=file_path)
            
            # 分析代码
            self._analyze_tree(tree)
            
        except SyntaxError as e:
            self.issues.append(CodeIssue(
                severity=Severity.HIGH,
                description=f"语法错误: {e.msg}",
                recommendation="修复语法错误后重新分析",
                line_number=e.lineno or 0,
                issue_type="语法错误",
                details=str(e)
            ))
        except Exception as e:
            print(f"分析文件时出错 {file_path}: {e}")
            
        return self.issues
    
    def _analyze_tree(self, tree: ast.AST):
        """分析 AST 树"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self._analyze_function(node)
            elif isinstance(node, ast.ClassDef):
                self._analyze_class(node)
    
    def _analyze_function(self, node: ast.FunctionDef):
        """分析函数"""
        # 检测函数长度
        func_length = node.end_lineno - node.lineno if node.end_lineno else 0
        if func_length > self.max_function_length:
            self.issues.append(CodeIssue(
                severity=Severity.MEDIUM,
                description=f"函数 '{node.name}' 过长 ({func_length} 行)",
                recommendation=f"将函数拆分为更小的函数，建议每函数不超过 {self.max_function_length} 行",
                line_number=node.lineno,
                issue_type="过长函数",
                details=f"当前长度: {func_length} 行，建议最大: {self.max_function_length} 行"
            ))
        
        # 检测参数数量
        param_count = len(node.args.args)
        if param_count > self.max_param_count:
            self.issues.append(CodeIssue(
                severity=Severity.MEDIUM,
                description=f"函数 '{node.name}' 参数过多 ({param_count} 个)",
                recommendation=f"考虑使用数据类或字典封装参数，或拆分函数",
                line_number=node.lineno,
                issue_type="参数过多",
                details=f"当前参数数: {param_count}，建议最大: {self.max_param_count}"
            ))
        
        # 检测圈复杂度
        complexity = self._calculate_complexity(node)
        if complexity > self.max_complexity:
            self.issues.append(CodeIssue(
                severity=Severity.HIGH,
                description=f"函数 '{node.name}' 复杂度过高 (复杂度: {complexity})",
                recommendation="简化控制流，提取复杂逻辑到独立函数",
                line_number=node.lineno,
                issue_type="复杂度过高",
                details=f"当前复杂度: {complexity}，建议最大: {self.max_complexity}"
            ))
    
    def _analyze_class(self, node: ast.ClassDef):
        """分析类"""
        # 检测类的大小
        methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
        if len(methods) > 20:
            self.issues.append(CodeIssue(
                severity=Severity.MEDIUM,
                description=f"类 '{node.name}' 方法过多 ({len(methods)} 个)",
                recommendation="考虑使用继承或组合来拆分类",
                line_number=node.lineno,
                issue_type="类过大",
                details=f"当前方法数: {len(methods)}"
            ))
        
        # 检测重复的方法名
        method_names = [m.name for m in methods]
        duplicates = [name for name in set(method_names) if method_names.count(name) > 1]
        if duplicates:
            self.issues.append(CodeIssue(
                severity=Severity.HIGH,
                description=f"类 '{node.name}' 中存在重复的方法名: {', '.join(duplicates)}",
                recommendation="重命名或删除重复的方法",
                line_number=node.lineno,
                issue_type="重复定义",
                details=f"重复的方法: {', '.join(duplicates)}"
            ))
    
    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """计算圈复杂度"""
        complexity = 1  # 基础复杂度
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        
        return complexity
    
    def analyze_multiple_files(self, file_paths: List[str]) -> dict:
        """
        分析多个 Python 文件
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            dict: 文件路径到问题列表的映射
        """
        results = {}
        for file_path in file_paths:
            results[file_path] = self.analyze_file(file_path)
        return results
    
    def analyze_directory(self, directory: str, recursive: bool = True) -> dict:
        """
        分析目录中的所有 Python 文件
        
        Args:
            directory: 目录路径
            recursive: 是否递归分析子目录
            
        Returns:
            dict: 文件路径到问题列表的映射
        """
        results = {}
        
        if not os.path.exists(directory):
            print(f"错误: 目录不存在 - {directory}")
            return results
        
        if recursive:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        results[file_path] = self.analyze_file(file_path)
        else:
            for file in os.listdir(directory):
                if file.endswith('.py'):
                    file_path = os.path.join(directory, file)
                    results[file_path] = self.analyze_file(file_path)
        
        return results
