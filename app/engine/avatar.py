"""Avatares — upload de imagem própria para o perfil."""
from __future__ import annotations

import uuid
from pathlib import Path

from app.config import UPLOADS_DIR

IS_IMAGE_PREFIX = "/static/uploads/"

# conteúdo -> extensão (apenas imagens raster; SVG fora por permitir scripts)
CONTENT_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

MAX_UPLOAD_BYTES = 1_500_000  # ~1,5 MB


def is_image_avatar(avatar: str | None) -> bool:
    return bool(avatar and avatar.startswith(IS_IMAGE_PREFIX))


def avatar_src(avatar: str | None) -> str | None:
    """Retorna o caminho se `avatar` for uma imagem enviada; senão None."""
    return avatar if is_image_avatar(avatar) else None


def save_avatar_upload(file) -> str:
    """Valida e grava a imagem enviada. Retorna a URL pública ou lança ValueError."""
    content_type = (file.content_type or "").lower()
    ext = CONTENT_EXT.get(content_type)
    if ext is None:
        raise ValueError("Formato de imagem não suportado (use PNG, JPG, GIF ou WEBP).")
    data = file.file.read() if hasattr(file.file, "read") else None
    size = len(data) if data is not None else 0
    if size == 0 or size > MAX_UPLOAD_BYTES:
        raise ValueError("A imagem precisa ter entre 1 byte e 1,5 MB.")
    filename = f"av-{uuid.uuid4().hex[:12]}{ext}"
    target = Path(UPLOADS_DIR) / filename
    target.write_bytes(data)
    return f"{IS_IMAGE_PREFIX}{filename}"


def remove_avatar_file(avatar: str | None) -> None:
    if not is_image_avatar(avatar):
        return
    name = avatar.rsplit("/", 1)[-1]
    target = Path(UPLOADS_DIR) / name
    try:
        target.unlink(missing_ok=True)
    except OSError:
        pass