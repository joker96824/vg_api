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

# 创建不同级别的日志文件处理器
debug_handler = RotatingFileHandler(
    filename=log_dir / "debug.log",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
debug_handler.setFormatter(log_format)
debug_handler.setLevel(logging.DEBUG)

info_handler = RotatingFileHandler(
    filename=log_dir / "api.log",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
info_handler.setFormatter(log_format)
info_handler.setLevel(logging.INFO)

error_handler = RotatingFileHandler(
    filename=log_dir / "error.log",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
error_handler.setFormatter(log_format)
error_handler.setLevel(logging.ERROR)

# 创建控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_format)
console_handler.setLevel(logging.DEBUG)

# 配置根日志记录器
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(debug_handler)
root_logger.addHandler(info_handler)
root_logger.addHandler(error_handler)
root_logger.addHandler(console_handler)

# 配置特定模块的日志级别
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING) 