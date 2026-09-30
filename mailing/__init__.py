# mailing/__init__.py
from mailing.sender import send_to_user, broadcast

__all__ = ["send_to_user", "broadcast"]