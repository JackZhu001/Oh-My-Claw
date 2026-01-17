"""
代码分析器模块

负责解析Python代码并计算基础代码度量指标。
"""

import ast
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class FunctionMetrics:
    """函数度量指标"""
    name: str
    start_line: int
    end_line: int
    length: int
    cyclomatic_complexity: int
    parameter_count: int
    nesting_depth: int
    docstring: Optional[str] = None


@dataclass
class ClassMetrics:
    """类度量指标"""
    name: str
    start_line: int
    end_line: int
    method_count: int
    attribute_count: int


@dataclass
class CodeMetrics:
    """代码度量指标总览"""
    file_path: str
    total_lines: int
    code_lines: int
    comment_lines: int
    blank_lines: int
    functions: List[FunctionMetrics] = field(default_factory=list)
    classes: List[ClassMetrics] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    duplicate_blocks: List[Dict[str, any]] = field(default_factory=list)


class CodeAnalyzer:
    """Python代码分析器"""
    
    # 配置阈值
    MAX_FUNCTION_LENGTH = 30
    MAX_COMPLEXITY = 10
    MAX_PARAMETERS = 5
    MAX_NESTING_DEPTH = 4
    
    def __init__(self, file_path: str):
        """
        初始化代码分析器
        
        Args:
            file_path: 要分析的Python文件路径
        """
        self.file_path = file_path
        self.source_code = ""
        self.tree = None
        self.metrics = None
    
    def _read_file(self) -> str:
        """读取文件内容"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"文件不存在: {self.file_path}")
        except Exception as e:
            raise Exception(f"读取文件失败: {e}")
    
    def _parse_ast(self, source: str) -> ast.AST:
        """解析AST"""
        try:
            return ast.parse(source)
        except SyntaxError as e:
            raise SyntaxError(f"语法错误: {e}")
    
    def _count_lines(self) -> tuple:
        """
        统计代码行数
        
        Returns:
            (总行数, 代码行数, 注释行数, 空白行数)
        """
        lines = self.source_code.split('\n')
        total_lines = len(lines)
        code_lines = 0
        comment_lines = 0
        blank_lines = 0
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                blank_lines += 1
            elif stripped.startswith('#'):
                comment_lines += 1
            else:
                code_lines += 1
        
        return total_lines, code_lines, comment_lines, blank_lines
    
    def _calculate_cyclomatic_complexity(self, node: ast.FunctionDef) -> int:
        """
        计算圈复杂度
        
        Args:
            node: 函数节点
            
        Returns:
            圈复杂度值
        """
        complexity = 1  # 基础复杂度
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, ast.comprehension):
                complexity += 1
        
        return complexity
    
    def _calculate_nesting_depth(self, node: ast.FunctionDef) -> int:
        """
        计算最大嵌套深度
        
        Args:
            node: 函数节点
            
        Returns:
            最大嵌套深度
        """
        max_depth = 0
        
        def visit_node(n, depth=0):
            nonlocal max_depth
            if depth > max_depth:
                max_depth = depth
            
            for child in ast.iter_child_nodes(n):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.With, ast.Try)):
                    visit_node(child, depth + 1)
                elif isinstance(child, ast.FunctionDef):
                    continue  # 不计算嵌套函数的深度
                else:
                    visit_node(child, depth)
        
        visit_node(node, 1)
        return max_depth
    
    def _extract_docstring(self, node: ast.FunctionDef) -> Optional[str]:
        """提取函数文档字符串"""
        docstring = ast.get_docstring(node)
        return docstring
    
    def _analyze_functions(self) -> List[FunctionMetrics]:
        """分析所有函数"""
        functions = []
        
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                start_line = node.lineno
                end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line
                length = end_line - start_line + 1
                
                metrics = FunctionMetrics(
                    name=node.name,
                    start_line=start_line,
                    end_line=end_line,
                    length=length,
                    cyclomatic_complexity=self._calculate_cyclomatic_complexity(node),
                    parameter_count=len(node.args.args),
                    nesting_depth=self._calculate_nesting_depth(node),
                    docstring=self._extract_docstring(node)
                )
                functions.append(metrics)
        
        return functions
    
    def _analyze_classes(self) -> List[ClassMetrics]:
        """分析所有类"""
        classes = []
        
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                start_line = node.lineno
                end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line
                
                method_count = sum(1 for n in node.body if isinstance(n, ast.FunctionDef))
                attribute_count = sum(
                    1 for n in ast.walk(node) 
                    if isinstance(n, ast.Assign) and any(
                        isinstance(target, ast.Name) for target in n.targets
                    )
                )
                
                metrics = ClassMetrics(
                    name=node.name,
                    start_line=start_line,
                    end_line=end_line,
                    method_count=method_count,
                    attribute_count=attribute_count
                )
                classes.append(metrics)
        
        return classes
    
    def _extract_imports(self) -> List[str]:
        """提取导入语句"""
        imports = []
        
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module if node.module else ''
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
        
        return imports
    
    def _detect_duplicate_code(self) -> List[Dict]:
        """
        检测重复代码块
        
        Returns:
            重复代码块列表
        """
        lines = self.source_code.split('\n')
        duplicates = []
        
        # 简单的重复代码检测：查找连续5行以上的重复
        min_block_size = 5
        blocks = {}
        
        for i in range(len(lines) - min_block_size + 1):
            block = '\n'.join(lines[i:i + min_block_size]).strip()
            if block and len(block) > 20:  # 忽略太短的块
                if block not in blocks:
                    blocks[block] = []
                blocks[block].append(i + 1)  # 行号从1开始
        
        # 找出重复的块
        for block, positions in blocks.items():
            if len(positions) > 1:
                duplicates.append({
                    'block': block[:100] + '...' if len(block) > 100 else block,
                    'positions': positions,
                    'count': len(positions)
                })
        
        return duplicates
    
    def analyze(self) -> CodeMetrics:
        """
        执行完整的代码分析
        
        Returns:
            CodeMetrics对象，包含所有度量指标
        """
        # 读取文件
        self.source_code = self._read_file()
        
        # 解析AST
        self.tree = self._parse_ast(self.source_code)
        
        # 统计行数
        total_lines, code_lines, comment_lines, blank_lines = self._count_lines()
        
        # 分析函数、类、导入和重复代码
        functions = self._analyze_functions()
        classes = self._analyze_classes()
        imports = self._extract_imports()
        duplicates = self._detect_duplicate_code()
        
        # 创建度量指标对象
        self.metrics = CodeMetrics(
            file_path=self.file_path,
            total_lines=total_lines,
            code_lines=code_lines,
            comment_lines=comment_lines,
            blank_lines=blank_lines,
            functions=functions,
            classes=classes,
            imports=imports,
            duplicate_blocks=duplicates
        )
        
        return self.metrics
