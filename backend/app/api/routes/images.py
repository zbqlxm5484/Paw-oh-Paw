"""반려견 사진 API(15.11, BE-34): 목록, 올리기, 열기(서명 URL), 지우기. 요청 검사 → services → 응답만 한다(11.3)."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, File, Form, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import AfterValidator, BeforeValidator, StringConstraints

from app.api.deps import CurrentStaff, DbSession, check_file_link
from app.core.config import get_settings
from app.core.dates import today_local
from app.models.enums import ImageKind
from app.schemas.chart import ImageListOut, ImageOut
from app.services import dog_images as image_service

router = APIRouter(tags=["차트 자료"])


def _blank_to_none(value: object) -> object:
    """폼은 빈 칸을 빈 문자열로 보낸다. 없는 것으로 본다(13.9)."""
    return None if isinstance(value, str) and not value.strip() else value


def _not_future(value: date | None) -> date | None:
    if value is not None and value > today_local():
        raise ValueError("미래 날짜는 쓸 수 없습니다")
    return value


CaptionText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
Caption = Annotated[CaptionText | None, BeforeValidator(_blank_to_none)]
TakenOn = Annotated[date | None, BeforeValidator(_blank_to_none), AfterValidator(_not_future)]


@router.get("/dogs/{dog_id}/images", response_model=ImageListOut)
def list_images(dog_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> ImageListOut:
    """찍은 날 오름차순(같으면 올린 순서). 항목의 file_url은 서명 URL이다."""
    return ImageListOut(items=image_service.list_images(db, staff.institution_id, dog_id))


@router.post("/dogs/{dog_id}/images", response_model=ImageOut, status_code=status.HTTP_201_CREATED)
def upload_image(
    dog_id: uuid.UUID,
    staff: CurrentStaff,
    db: DbSession,
    file: Annotated[UploadFile, File()],
    kind: Annotated[ImageKind, Form()],
    taken_on: Annotated[TakenOn, Form()] = None,
    caption: Annotated[Caption, Form()] = None,
) -> ImageOut:
    """사진을 올린다. 사람 얼굴을 가려 다시 저장하고 원본은 두지 않는다(12.5 사진). XRAY는 가리지 않는다."""
    return image_service.upload_image(
        db,
        institution_id=staff.institution_id,
        staff_id=staff.id,
        dog_id=dog_id,
        upload=file,
        kind=kind.value,
        taken_on=taken_on,
        caption=caption,
    )


@router.get("/images/{image_id}/file", response_class=FileResponse)
def get_image_file(image_id: uuid.UUID, db: DbSession, exp: str | None = None, sig: str | None = None) -> FileResponse:
    """사진 열기. 로그인 토큰 없이 서명(exp·sig)으로 연다.

    서명이 없거나 틀리거나 지났으면 403 FILE_LINK_EXPIRED(DB를 보기 전에 확인한다). 사진이 없으면 404.
    """
    check_file_link(image_service.IMAGE_API_PATH.format(image_id=image_id), exp, sig)
    path, media_type = image_service.image_file(db, image_id)
    cache_control = f"private, max-age={get_settings().FILE_URL_TTL_SEC}"
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": cache_control})


@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(image_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> Response:
    """사진을 지운다(파일 → 행). 얼굴이 가려지지 않은 사진을 바로 지울 수 있게 둔 것이다(12.5 사진)."""
    image_service.delete_image(db, staff.institution_id, image_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
