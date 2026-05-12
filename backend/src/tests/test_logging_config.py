"""系统日志配置测试。"""

import logging
from pathlib import Path
import shutil
import tempfile
import unittest

from src.core.logging import setup_logging


class LoggingConfigTests(unittest.TestCase):
    def test_setup_logging_writes_separate_level_files(self) -> None:
        root_logger = logging.getLogger()
        original_handlers = list(root_logger.handlers)
        original_level = root_logger.level

        for handler in original_handlers:
            root_logger.removeHandler(handler)

        tmp_dir = tempfile.mkdtemp()
        try:
            log_dir = Path(tmp_dir)
            setup_logging("DEBUG", log_dir=log_dir)

            logger = logging.getLogger("tests.logging_config")
            logger.debug("调试日志")
            logger.info("信息日志")
            logger.warning("警告日志")
            logger.error("错误日志")

            for handler in root_logger.handlers:
                handler.flush()

            self.assertIn("调试日志", (log_dir / "debug.log").read_text(encoding="utf-8"))
            self.assertIn("信息日志", (log_dir / "info.log").read_text(encoding="utf-8"))
            self.assertIn("警告日志", (log_dir / "warning.log").read_text(encoding="utf-8"))
            self.assertIn("错误日志", (log_dir / "error.log").read_text(encoding="utf-8"))

            backend_log = (log_dir / "backend.log").read_text(encoding="utf-8")
            self.assertIn("调试日志", backend_log)
            self.assertIn("错误日志", backend_log)

            handler_count = len(root_logger.handlers)
            setup_logging("DEBUG", log_dir=log_dir)
            self.assertEqual(len(root_logger.handlers), handler_count)
        finally:
            for handler in list(root_logger.handlers):
                handler.close()
                root_logger.removeHandler(handler)
            for handler in original_handlers:
                root_logger.addHandler(handler)
            root_logger.setLevel(original_level)
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
