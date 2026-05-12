"""SMTP 邮件发送服务。"""

from email.message import EmailMessage
import smtplib
import ssl

from src.core.config import Settings
from src.core.exceptions import AppException
from src.core.logging import get_logger

logger = get_logger(__name__)


class EmailService:
    """通过配置好的 SMTP 账号发送认证邮件。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send_verification_code(self, email: str, code: str, purpose: str, expires_minutes: int) -> None:
        """发送短期有效的邮箱验证码。"""

        if not self._is_configured():
            raise AppException(
                500,
                "EMAIL_SERVICE_NOT_CONFIGURED",
                "邮件发送服务尚未配置，请先配置 QQ 邮箱 SMTP 信息。",
            )

        subject = "轻灵厨房验证码"
        purpose_text = "注册账号" if purpose == "register" else "邮箱验证码登录"
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.settings.smtp_from or self.settings.smtp_user
        message["To"] = email
        message.set_content(
            "\n".join(
                [
                    f"你正在进行轻灵厨房{purpose_text}操作。",
                    f"验证码：{code}",
                    f"验证码 {expires_minutes} 分钟内有效，请勿转发给他人。",
                    "",
                    "如果不是你本人操作，可以忽略这封邮件。",
                ]
            )
        )

        try:
            if self.settings.smtp_use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                    self.settings.smtp_host,
                    self.settings.smtp_port,
                    timeout=self.settings.smtp_timeout_seconds,
                    context=context,
                ) as smtp:
                    smtp.login(self.settings.smtp_user, self.settings.smtp_password)
                    smtp.send_message(message)
                logger.info("Verification email sent through SMTP SSL.", extra={"email": email, "purpose": purpose})
                return

            with smtplib.SMTP(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=self.settings.smtp_timeout_seconds,
            ) as smtp:
                if self.settings.smtp_use_tls:
                    smtp.starttls(context=ssl.create_default_context())
                smtp.login(self.settings.smtp_user, self.settings.smtp_password)
                smtp.send_message(message)
            logger.info("Verification email sent through SMTP.", extra={"email": email, "purpose": purpose})
        except smtplib.SMTPException as exc:
            logger.warning("Verification email SMTP send failed.", exc_info=exc)
            raise AppException(
                502,
                "EMAIL_SEND_FAILED",
                "验证码邮件发送失败，请稍后重试。",
            ) from exc
        except OSError as exc:
            logger.warning("Verification email SMTP server unreachable.", exc_info=exc)
            raise AppException(
                502,
                "EMAIL_SERVER_UNREACHABLE",
                "无法连接邮件服务器，请检查 SMTP 配置。",
            ) from exc

    def _is_configured(self) -> bool:
        return bool(
            self.settings.smtp_host
            and self.settings.smtp_port
            and self.settings.smtp_user
            and self.settings.smtp_password
        )
