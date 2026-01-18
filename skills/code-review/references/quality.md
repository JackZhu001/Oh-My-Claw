# 代码质量检查规则

## 🟠 高优先级

### God Class（上帝类）
- **规则**: 单文件 > 500 行
- **检测**: `wc -l *.py | sort -rn | head`
- **修复**: 提取子类或模块

### Long Method（长函数）
- **规则**: 单函数 > 50 行
- **检测**: AST 分析或人工审查
- **修复**: 提取私有方法

### 高圈复杂度
- **规则**: 嵌套 if/for > 3 层
- **修复**: 早返回、策略模式

## 🟡 中等

### 重复代码
- **规则**: 相似代码块 > 10 行出现 2+ 次
- **修复**: 提取公共函数

### 魔法数字
```python
# 避免
if retry_count > 3:

# 推荐
MAX_RETRIES = 3
if retry_count > MAX_RETRIES:
```

### 过长参数列表
- **规则**: 函数参数 > 5 个
- **修复**: 使用 dataclass 或 config 对象

## 🟢 低优先级

### 缺少类型提示
```python
# 推荐
def process(data: list[str]) -> dict[str, int]:
```

### 缺少文档字符串
```python
# 公共 API 必须有
def public_method(arg: str) -> None:
    """一句话描述功能。
    
    Args:
        arg: 参数说明
    """
```

### 命名不规范
- 类名: `PascalCase`
- 函数/变量: `snake_case`
- 常量: `UPPER_SNAKE_CASE`
