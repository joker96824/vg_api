import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# 创建日志目录
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# 配置日志格式
log_format = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 创建文件处理器
file_handler = RotatingFileHandler(
    filename=log_dir / "app.log",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(log_format)
file_handler.setLevel(logging.DEBUG)

# 创建控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_format)
console_handler.setLevel(logging.DEBUG)

# 配置根日志记录器
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# 配置特定模块的日志级别
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO) 