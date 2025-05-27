# 项目结构说明

## 目录结构

```
.
├── alembic/                # 数据库迁移相关文件
├── config/                 # 配置文件目录
├── docs/                   # 项目文档
├── logs/                   # 日志文件目录
├── scripts/               # 脚本文件目录
├── src/                   # 源代码目录
│   ├── api/              # API层
│   │   └── v1/          # API版本1
│   │       ├── endpoints/  # 路由处理器
│   │       └── schemas/    # API请求/响应模型（已迁移到core/schemas）
│   ├── core/             # 核心功能
│   │   ├── auth/         # 认证相关
│   │   ├── config/       # 核心配置
│   │   ├── models/       # 数据库模型
│   │   ├── schemas/      # 数据模型定义
│   │   ├── services/     # 业务服务
│   │   └── utils/        # 工具函数
│   ├── templates/        # 模板文件
│   └── main.py           # 应用入口
├── tests/                # 测试文件目录
├── .editorconfig         # 编辑器配置
├── .gitignore           # Git忽略文件
├── README.md            # 项目说明文档
├── requirements.txt     # 项目依赖
└── setup.py            # 项目安装配置
```

## 文件说明

### 配置文件
- `config/` - 存放所有配置文件
  - `settings.py` - 主配置文件
  - `database.py` - 数据库配置

### 源代码
- `src/` - 主要源代码目录
  - `main.py` - FastAPI应用入口
  - `api/` - API层
    - `v1/endpoints/` - API路由处理器
  - `core/` - 核心功能
    - `auth/` - 认证相关功能
    - `config/` - 核心配置
    - `models/` - SQLAlchemy数据库模型
    - `schemas/` - Pydantic数据模型定义
    - `services/` - 业务服务层
    - `utils/` - 工具函数（所有通用工具函数统一放在这里）
  - `templates/` - 模板文件

### 数据库
- `alembic/` - 数据库迁移相关文件
  - `versions/` - 迁移版本文件
  - `env.py` - 迁移环境配置
  - `script.py.mako` - 迁移脚本模板

### 测试
- `tests/` - 测试文件目录（所有测试文件统一放在这里）
  - `conftest.py` - 测试配置
  - `test_*.py` - 测试文件

### 文档
- `docs/` - 项目文档
  - `PROJECT_STRUCTURE.md` - 项目结构说明（本文档）

### 脚本
- `scripts/` - 脚本文件目录（所有脚本文件统一放在这里）
  - `import_test_data.py` - 测试数据导入脚本
  - `check_tables.py` - 数据库表检查脚本

### 日志
- `logs/` - 日志文件目录
- `app.log` - 应用日志文件

## 日志规范

### 日志文件结构
```
logs/                           # 日志目录
├── api.log                     # API请求响应日志
├── error.log                   # 错误日志
└── debug.log                   # 调试日志
```

### 日志记录规范

1. 日志级别使用规范
   - ERROR: 系统错误、异常、失败操作
   - WARNING: 警告信息、潜在问题
   - INFO: 重要操作、状态变更
   - DEBUG: 调试信息、详细流程

2. 日志格式规范
   ```
   [时间] [操作] [级别] | 消息 | 上下文信息
   ```
   示例：
   ```
   ==================================================
   [2024-03-21 10:30:45] [获取卡牌列表] [INFO] | 请求 | 用户ID=123 | 查询参数={"name": "测试"}
   ==================================================
   ```

3. 日志分隔符规范
   - 使用50个等号作为分隔符：`==================================================`
   - 分隔符使用场景：
     - 每次请求开始和结束
     - 不同操作之间
     - 错误日志前后
     - 重要操作前后
   - 分隔符示例：
     ```
     ==================================================
     [2024-03-21 10:30:45] [获取卡牌列表] [INFO] | 请求开始
     [2024-03-21 10:30:45] [获取卡牌列表] [INFO] | 参数 | 用户ID=123
     [2024-03-21 10:30:46] [获取卡牌列表] [INFO] | 响应 | 结果=成功
     ==================================================
     ```

4. 日志内容规范
   - 请求日志：记录请求参数、用户信息
   - 响应日志：记录响应结果、处理时间
   - 错误日志：记录错误详情、堆栈信息
   - 警告日志：记录警告原因、影响范围
   - 调试日志：记录详细流程、中间状态

5. 日志工具使用规范
   ```python
   from src.core.utils.logger import APILogger
   
   # 记录请求
   APILogger.log_request("操作名称", 用户ID=user_id, 参数=params)
   
   # 记录响应
   APILogger.log_response("操作名称", 结果=result)
   
   # 记录警告
   APILogger.log_warning("操作名称", "警告消息", 原因=reason)
   
   # 记录错误
   APILogger.log_error("操作名称", error, 上下文=context)
   
   # 记录调试信息
   APILogger.log_debug("操作名称", 调试信息=debug_info)
   ```

6. 日志记录注意事项
   - 敏感信息（如密码、token）必须脱敏
   - 大量数据需要截断或摘要
   - 异常信息需要完整记录
   - 关键操作必须记录日志
   - 避免重复记录相同信息

7. 日志文件管理
   - 按天切割日志文件
   - 定期归档历史日志
   - 设置日志文件大小限制
   - 配置日志保留时间

8. 日志监控
   - 监控错误日志数量
   - 监控异常模式
   - 监控性能问题
   - 监控安全事件

### 日志工具类说明

`src/core/utils/logger.py` 中的 `APILogger` 类提供以下功能：

1. 基础日志方法
   - `log_request`: 记录请求信息
   - `log_response`: 记录响应信息
   - `log_warning`: 记录警告信息
   - `log_error`: 记录错误信息
   - `log_debug`: 记录调试信息

2. 辅助方法
   - `_format_log_data`: 格式化日志数据
   - `_get_logger`: 获取logger实例
   - `format_card_info`: 格式化卡牌信息

3. 使用示例
   ```python
   # 在API端点中使用
   @router.get("/cards")
   async def get_cards():
       try:
           APILogger.log_request("获取卡牌列表", 参数=params)
           result = await service.get_cards()
           APILogger.log_response("获取卡牌列表", 结果=result)
           return result
       except Exception as e:
           APILogger.log_error("获取卡牌列表", e)
           raise
   ```

### 日志配置

1. 日志配置项
   ```python
   LOGGING_CONFIG = {
       "version": 1,
       "disable_existing_loggers": False,
       "formatters": {
           "default": {
               "format": "[%(asctime)s] [%(name)s] [%(levelname)s] | %(message)s"
           }
       },
       "handlers": {
           "console": {
               "class": "logging.StreamHandler",
               "formatter": "default"
           },
           "file": {
               "class": "logging.handlers.RotatingFileHandler",
               "filename": "logs/api.log",
               "maxBytes": 10485760,  # 10MB
               "backupCount": 5
           }
       },
       "loggers": {
           "api": {
               "handlers": ["console", "file"],
               "level": "INFO"
           }
       }
   }
   ```

2. 环境变量配置
   ```
   LOG_LEVEL=INFO
   LOG_FORMAT=default
   LOG_FILE=logs/api.log
   LOG_MAX_BYTES=10485760
   LOG_BACKUP_COUNT=5
   ```

## 文件命名规范

1. Python文件使用小写字母，单词间用下划线连接
2. 类名使用大驼峰命名法
3. 函数和变量使用小写字母，单词间用下划线连接
4. 常量使用大写字母，单词间用下划线连接

## 目录使用规范

1. `api/v1/endpoints/` - 存放所有API路由处理器
2. `core/schemas/` - 存放所有数据模型定义
3. `core/models/` - 存放所有数据库模型
4. `core/services/` - 存放所有业务服务
5. `core/utils/` - 存放所有通用工具函数
6. `scripts/` - 存放所有脚本文件
7. `tests/` - 存放所有测试文件

## 新增文件规范

1. 新增API端点：
   - 在`src/api/v1/endpoints/`下创建对应的路由文件
   - 在`src/core/schemas/`下创建对应的请求/响应模型

2. 新增服务：
   - 在`src/core/services/`下创建对应的服务文件
   - 在`src/core/schemas/`下创建对应的数据模型

3. 新增数据库模型：
   - 在`src/core/models/`下创建对应的模型文件
   - 使用Alembic创建数据库迁移

4. 新增工具函数：
   - 在`src/core/utils/`下创建对应的工具文件
   - 确保工具函数是通用的，不包含业务逻辑

5. 新增测试：
   - 在`tests/`下创建对应的测试文件
   - 遵循`test_*.py`的命名规范

6. 新增脚本：
   - 在`scripts/`下创建对应的脚本文件
   - 确保脚本文件有清晰的用途说明

## 变更记录

| 日期 | 变更内容 | 变更原因 | 执行人 |
|------|----------|----------|--------|
| 2024-03-21 | 将API请求/响应模型从`api/v1/schemas/`迁移到`core/schemas/` | 统一模型管理，提高复用性 | Claude |
| 2024-03-21 | 统一工具函数、脚本和测试文件的位置 | 规范化项目结构，避免重复 | Claude |

## 工作流程

### 新增功能工作流程

1. 查阅文档
   - 首先阅读`PROJECT_STRUCTURE.md`文档
   - 确认新功能应该放在哪个目录
   - 检查是否需要创建新的目录

2. 创建文件
   - 按照文档规范创建新文件
   - 遵循命名规范
   - 确保文件位置正确

3. 更新文档
   - 如果新增了目录，更新目录结构
   - 如果新增了文件类型，更新文件说明
   - 在变更记录中添加新的记录

4. 提交代码
   - 确保新文件符合项目结构
   - 提交代码时包含文档更新

### 修改现有功能工作流程

1. 查阅文档
   - 确认要修改的文件位置
   - 了解相关的依赖关系

2. 进行修改
   - 遵循现有的代码风格
   - 保持目录结构不变

3. 更新文档
   - 如果修改涉及结构变化，更新文档
   - 在变更记录中添加新的记录

### 文档维护

1. 定期检查
   - 每周检查文档是否与实际结构一致
   - 确保所有变更都已记录

2. 版本控制
   - 文档变更需要单独提交
   - 提交信息需要说明文档变更原因

3. 团队协作
   - 所有团队成员都需要了解文档内容
   - 新成员加入时需要先阅读文档

## 注意事项

1. 禁止直接创建新文件而不更新文档
2. 禁止在文档未指定的位置创建文件
3. 禁止修改已删除的目录或文件
4. 所有结构变更必须记录在变更记录中
5. 文档更新必须与代码变更同步进行
6. 所有工具函数必须放在`src/core/utils/`目录下
7. 所有脚本文件必须放在`scripts/`目录下
8. 所有测试文件必须放在`tests/`目录下
9. 环境变量变更时，禁止直接修改代码中的配置值，必须提出要求由管理员添加到`.env`文件中

## 注意事项

1. 禁止直接创建新文件而不更新文档
2. 禁止在文档未指定的位置创建文件
3. 禁止修改已删除的目录或文件
4. 所有结构变更必须记录在变更记录中
5. 文档更新必须与代码变更同步进行
6. 所有工具函数必须放在`src/core/utils/`目录下
7. 所有脚本文件必须放在`scripts/`目录下
8. 所有测试文件必须放在`tests/`目录下 