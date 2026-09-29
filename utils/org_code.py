import base64
import hashlib

from save_config import settings


# Секретный ключ для подписи кодов.
# Возьмите значение из settings, чтобы он не лежал в коде.
_SECRET = settings.ORG_CODE_SECRET.encode()


def _sign(data: bytes) -> bytes:
    """Возвращает короткую подпись (4 байта) для данных."""
    digest = hashlib.sha256(_SECRET + data).digest()
    return digest[:4]


def encode_org_id(org_id: int) -> str:
    """
    Кодирует ID организации в короткий код.
    Пример: 42 → 'KgAAAOh1'
    """
    payload = org_id.to_bytes(4, "big")     # 4 байта под ID (до 4 млрд)
    signature = _sign(payload)              # 4 байта подписи
    raw = payload + signature               # 8 байт
    code = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return code


def decode_org_code(code: str) -> int:
    """
    Расшифровывает код обратно в ID организации.
    Бросает ValueError, если код битый или подпись не совпадает.
    """
    # Восстанавливаем padding для base64
    padding = "=" * (-len(code) % 4)
    try:
        raw = base64.urlsafe_b64decode(code + padding)
    except Exception as e:
        raise ValueError("Некорректный код организации") from e

    if len(raw) != 8:
        raise ValueError("Некорректный код организации")

    payload, signature = raw[:4], raw[4:]

    if _sign(payload) != signature:
        raise ValueError("Неверный код организации")

    return int.from_bytes(payload, "big")