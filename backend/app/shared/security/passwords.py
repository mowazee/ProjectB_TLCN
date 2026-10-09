"""Hash mật khẩu Argon2 (NFR-02)."""

import secrets

from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()
# So sánh với hash giả khi username không tồn tại để không lộ user qua thời gian phản hồi
_DUMMY = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    if hashed is None:
        _hasher.verify(password, _DUMMY)
        return False
    return _hasher.verify(password, hashed)
