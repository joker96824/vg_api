# Vanguard API

这是一个基于 FastAPI 构建的 Vanguard 卡牌游戏 API 服务。

## 功能特点

- 基于 FastAPI 框架
- 异步数据库操作
- PostgreSQL 数据库支持
- 完整的 API 文档
- 支持热重载开发
- 规范的代码结构

## 技术栈

- Python 3.11+
- FastAPI
- SQLAlchemy
- PostgreSQL
- Uvicorn
- Pydantic

## 项目结构

```
vg_api/
├── alembic/          # 数据库迁移
├── config/           # 配置文件
├── docs/            # 文档
├── scripts/         # 脚本文件
├── src/             # 源代码
│   ├── api/         # API 路由
│   ├── core/        # 核心功能
│   └── utils/       # 工具函数
├── tests/           # 测试文件
├── .env             # 环境变量
├── .gitignore       # Git 忽略文件
├── README.md        # 项目说明
├── requirements.txt # 依赖包
└── setup.py         # 安装配置
```

## 安装步骤

1. 克隆项目
```bash
git clone <repository-url>
cd vg_api
```

2. 创建虚拟环境
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. 安装依赖
```bash
pip install -r requirements.txt
pip install -e .
```

4. 配置环境变量
复制 `.env.example` 到 `.env` 并修改配置：
```bash
cp .env.example .env
```

5. 启动服务
```bash
uvicorn src.main:app --reload --log-level debug
```

## API 文档

启动服务后，可以通过以下地址访问 API 文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 开发指南

1. 代码风格
- 遵循 PEP 8 规范
- 使用 Black 进行代码格式化
- 使用 isort 进行导入排序

2. 提交规范
- feat: 新功能
- fix: 修复问题
- docs: 文档修改
- style: 代码格式修改
- refactor: 代码重构
- test: 测试用例修改
- chore: 其他修改

## 测试

运行测试：
```bash
pytest
```

## 部署

1. 生产环境配置
- 修改 `.env` 文件中的环境变量
- 设置 `DEBUG=False`
- 配置适当的数据库连接

2. 使用 gunicorn 部署
```bash
gunicorn src.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## 许可证

[MIT License](LICENSE) 