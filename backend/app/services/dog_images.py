"""반려견 사진(BE-34, 명세 12.5 사진, 13.9, 15.11). 얼굴을 가린 사진만 저장하고 원본은 두지 않는다.

흐름: 반려견 확인 → 받은 바이트 검사(크기 → 형식 → 화소 → 풀기) → 얼굴 가리기·다시 쓰기(video/photo.py)
→ 저장소에 쓰기(키를 db.info["created_files"]에 기록) → 행. 검사에 걸리면 아무것도 남기지 않는다.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.dates import today_local
from app.core.errors import AppError, ErrorCode
from app.models import Dog, DogImage
from app.models.enums import ImageKind
from app.schemas.chart import ImageOut
from app.schemas.common import StaffBriefOut
from app.services.dogs import get_dog, in_institution
from app.storage.base import StorageService, get_storage
from app.storage.keys import image_key
from app.storage.local import LocalStorage
from app.video.photo import (
    CONTENT_TYPES,
    FaceFinder,
    PhotoFormatError,
    PhotoTooLargeError,
    PhotoUnreadableError,
    prepare_photo,
)

logger = logging.getLogger(__name__)

IMAGE_API_PATH = "/api/v1/images/{image_id}/file"
MB = 1024 * 1024
# 13.9: 20 MB, 4,000만 화소
IMAGE_MAX_MB = 20
IMAGE_MAX_MEGAPIXELS = 40
# 방사선 사진은 얼굴이 없고 잘못 가리면 판독할 자리가 지워진다(12.5 사진)
UNMASKED_KINDS = (ImageKind.XRAY.value,)


def _too_large() -> AppError:
    return AppError(ErrorCode.IMAGE_TOO_LARGE, {"max_mb": IMAGE_MAX_MB, "max_mp": IMAGE_MAX_MEGAPIXELS})


def to_image_out(image: DogImage, storage: StorageService) -> ImageOut:
    file_url, expires_at = storage.file_url(image.file_key, IMAGE_API_PATH.format(image_id=image.id))
    return ImageOut(
        id=image.id,
        taken_on=image.taken_on,
        kind=image.kind,
        caption=image.caption,
        width=image.width,
        height=image.height,
        masked_faces=image.masked_faces,
        staff=StaffBriefOut.model_validate(image.staff),
        created_at=image.created_at,
        file_url=file_url,
        url_expires_at=expires_at,
    )


def list_images(db: Session, institution_id: uuid.UUID, dog_id: uuid.UUID) -> list[ImageOut]:
    """GET /dogs/{dog_id}/images. 찍은 날 오름차순, 같으면 올린 순서다."""
    dog = get_dog(db, institution_id, dog_id)
    rows = db.scalars(
        select(DogImage)
        .where(DogImage.dog_id == dog.id)
        .options(joinedload(DogImage.staff))
        .order_by(DogImage.taken_on, DogImage.created_at, DogImage.id)
    ).all()
    storage = get_storage()
    return [to_image_out(row, storage) for row in rows]


def upload_image(
    db: Session,
    *,
    institution_id: uuid.UUID,
    staff_id: uuid.UUID,
    dog_id: uuid.UUID,
    upload: UploadFile,
    kind: str,
    taken_on: date | None,
    caption: str | None,
    detect_faces: FaceFinder | None = None,
) -> ImageOut:
    """POST /dogs/{dog_id}/images. 검사 순서는 13.9다. 얼굴 검출이 실패하면 저장하지 않고 예외를 올린다(500)."""
    dog = get_dog(db, institution_id, dog_id)
    upload.file.seek(0)
    data = upload.file.read(IMAGE_MAX_MB * MB + 1)
    if len(data) > IMAGE_MAX_MB * MB:
        raise _too_large()
    try:
        photo = prepare_photo(
            data,
            mask_faces=kind not in UNMASKED_KINDS,
            max_pixels=IMAGE_MAX_MEGAPIXELS * 1_000_000,
            detect_faces=detect_faces,
        )
    except PhotoFormatError:
        raise AppError(ErrorCode.IMAGE_FORMAT) from None
    except PhotoTooLargeError:
        raise _too_large() from None
    except PhotoUnreadableError:
        raise AppError(ErrorCode.IMAGE_UNREADABLE) from None

    image_id = uuid.uuid4()
    key = image_key(institution_id, dog.id, image_id, photo.ext)
    storage = get_storage()
    storage.write_bytes(key, photo.data)
    db.info.setdefault("created_files", []).append(key)
    image = DogImage(
        id=image_id,
        dog_id=dog.id,
        taken_on=taken_on or today_local(),
        kind=kind,
        caption=caption,
        file_key=key,
        width=photo.width,
        height=photo.height,
        masked_faces=photo.masked_faces,
        staff_id=staff_id,
    )
    db.add(image)
    db.flush()
    db.refresh(image)
    logger.info(
        "dog image stored image=%s kind=%s size=%dx%d bytes=%d masked_faces=%d",
        image.id,
        kind,
        photo.width,
        photo.height,
        len(photo.data),
        photo.masked_faces,
    )
    return to_image_out(image, storage)


def _get_image(db: Session, institution_id: uuid.UUID, image_id: uuid.UUID) -> DogImage:
    """없거나 다른 기관·휴지통의 반려견의 사진이면 똑같이 404 NOT_FOUND(15.1)."""
    image = db.scalars(
        select(DogImage)
        .join(Dog, DogImage.dog_id == Dog.id)
        .where(DogImage.id == image_id, in_institution(institution_id))
    ).one_or_none()
    if image is None:
        raise AppError(ErrorCode.NOT_FOUND)
    return image


def delete_image(db: Session, institution_id: uuid.UUID, image_id: uuid.UUID) -> None:
    """DELETE /images/{id}. 파일을 먼저, 그다음 행을 지운다(12.5)."""
    image = _get_image(db, institution_id, image_id)
    get_storage().delete(image.file_key)
    db.delete(image)
    db.flush()


def image_file(db: Session, image_id: uuid.UUID) -> tuple[Path, str]:
    """GET /images/{id}/file이 FileResponse에 넘길 (경로, Content-Type). 서명 확인은 라우트가 먼저 한다.

    사진이 없거나 파일이 없으면 404 NOT_FOUND. 저장소가 S3면 file_url이 S3 주소라 이 API는 쓰이지 않고,
    불리면 404다(11.11).
    """
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise AppError(ErrorCode.NOT_FOUND)
    image = db.get(DogImage, image_id)
    if image is None:
        raise AppError(ErrorCode.NOT_FOUND)
    path = storage.path(image.file_key)
    if not path.is_file():
        raise AppError(ErrorCode.NOT_FOUND)
    return path, CONTENT_TYPES[image.file_key.rsplit(".", 1)[-1]]
