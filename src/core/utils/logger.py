import logging
from typing import Any, Dict, Optional
from datetime import datetime

class APILogger:
    """API日志记录工具类"""
    
    SEPARATOR = "=" * 50
    
    @staticmethod
    def _format_log_data(**kwargs) -> str:
        """格式化日志数据"""
        return " | ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)

    @staticmethod
    def _get_logger() -> logging.Logger:
        """获取logger实例"""
        return logging.getLogger("api")

    @classmethod
    def _log_with_separator(cls, logger: logging.Logger, level: int, msg: str) -> None:
        """带分隔符的日志记录"""
        logger.log(level, f"\n{cls.SEPARATOR}\n{msg}\n{cls.SEPARATOR}")

    @classmethod
    def log_request(cls, operation: str, **kwargs) -> None:
        """记录请求日志"""
        logger = cls._get_logger()
        log_data = cls._format_log_data(**kwargs)
        msg = f"[{operation}] 请求 | {log_data}"
        cls._log_with_separator(logger, logging.INFO, msg)

    @classmethod
    def log_response(cls, operation: str, **kwargs) -> None:
        """记录响应日志"""
        logger = cls._get_logger()
        log_data = cls._format_log_data(**kwargs)
        msg = f"[{operation}] 响应 | {log_data}"
        cls._log_with_separator(logger, logging.INFO, msg)

    @classmethod
    def log_warning(cls, operation: str, message: str, **kwargs) -> None:
        """记录警告日志"""
        logger = cls._get_logger()
        log_data = cls._format_log_data(**kwargs)
        msg = f"[{operation}] 警告 | {message} | {log_data}"
        cls._log_with_separator(logger, logging.WARNING, msg)

    @classmethod
    def log_error(cls, operation: str, error: Exception, **kwargs) -> None:
        """记录错误日志"""
        logger = cls._get_logger()
        log_data = cls._format_log_data(**kwargs)
        msg = f"[{operation}] 错误 | {str(error)} | {log_data}"
        cls._log_with_separator(logger, logging.ERROR, msg)

    @classmethod
    def log_debug(cls, operation: str, **kwargs) -> None:
        """记录调试日志"""
        logger = cls._get_logger()
        log_data = cls._format_log_data(**kwargs)
        msg = f"[{operation}] 调试 | {log_data}"
        cls._log_with_separator(logger, logging.DEBUG, msg)

    @staticmethod
    def format_card_info(card: Any) -> Dict[str, Any]:
        """格式化卡牌信息用于日志记录"""
        return {
            "卡牌ID": str(card.id),
            "卡牌名称": card.name_cn,
            "卡牌编号": card.card_code,
            "卡牌类型": card.type,
            "属性": card.attribute,
            "等级": card.level,
            "攻击力": card.atk,
            "防御力": card.def_
        } 