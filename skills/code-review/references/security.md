# 安全检查清单

按优先级逐项检查，发现问题立即记录。

## 🔴 严重（必须修复）

### SQL 注入
```python
# 危险模式
f"SELECT * FROM users WHERE id = {user_id}"
"SELECT * FROM users WHERE id = " + user_id

# 安全模式
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
```

**Grep**: `pattern="f[\"']SELECT|f[\"']INSERT|f[\"']UPDATE|f[\"']DELETE"`

### 命令注入
```python
# 危险模式
os.system(f"rm {filename}")
subprocess.run(f"ls {path}", shell=True)

# 安全模式
subprocess.run(["rm", filename], shell=False)
```

**Grep**: `pattern="os\.system\(f|subprocess.*shell=True"`

### 路径遍历
```python
# 危险模式
Path(user_input)  # 可传入 ../../etc/passwd

# 安全模式
path = Path(user_input).resolve()
if not path.is_relative_to(base_dir):
    raise ValueError("路径越界")
```

**Grep**: `pattern="Path\(.*\)(?!.*is_relative_to)"`

## 🟠 高优先级

### 硬编码密钥
```python
# 危险
API_KEY = "sk-xxx"
password = "admin123"

# 安全
API_KEY = os.getenv("API_KEY")
```

**Grep**: `pattern="(API_KEY|SECRET|PASSWORD|TOKEN)\s*=\s*[\"'][^\"']+[\"']" -i=true`

### 弱加密
```python
# 避免
import md5
hashlib.md5(password)

# 推荐
import bcrypt
bcrypt.hashpw(password, bcrypt.gensalt())
```

## 🟡 中等

### 通用异常捕获
```python
# 避免
except Exception:
    pass

# 推荐
except (ValueError, KeyError) as e:
    logger.error(f"Specific error: {e}")
```

**Grep**: `pattern="except\s+Exception\s*:"`

### 调试代码残留
**Grep**: `pattern="print\(|console\.log\(|debugger|pdb\.set_trace"`
