"""Cổng gửi email EmailSender (FR-18, SDD v0.13; Đặc tả đề tài v0.13 mục 4.3).

SmtpEmailSender dùng cấu hình SMTP_* trong .env (Gmail: smtp.gmail.com:587 + app password; dev: Mailpit
localhost:1025). Chưa cấu hình SMTP_HOST thì email_enabled() = False và tính năng chia sẻ ra ngoài bị ẩn.
Mật khẩu SMTP chỉ nằm ở backend, không bao giờ trả ra client.
"""

import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

from app.shared.config import settings


class EmailSender(Protocol):
    def send(self, to: str, subject: str, text: str, html: str | None = None) -> None: ...


class SmtpEmailSender:
    def send(self, to: str, subject: str, text: str, html: str | None = None) -> None:
        msg = EmailMessage()
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text)
        if html:
            msg.add_alternative(html, subtype="html")
        context = ssl.create_default_context()
        if settings.SMTP_SSL:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context, timeout=20) as s:
                self._login_send(s, msg)
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as s:
                if settings.SMTP_STARTTLS:
                    s.starttls(context=context)
                self._login_send(s, msg)

    @staticmethod
    def _login_send(s: smtplib.SMTP, msg: EmailMessage) -> None:
        if settings.SMTP_USER:
            s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        s.send_message(msg)


_override: EmailSender | None = None


def email_enabled() -> bool:
    return bool(settings.SMTP_HOST) or _override is not None


def get_email_sender() -> EmailSender:
    return _override if _override is not None else SmtpEmailSender()


def set_email_sender(sender: EmailSender | None) -> None:
    """Thay sender (test dùng sender giả ghi lại thư)."""
    global _override
    _override = sender
