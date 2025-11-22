from pydantic import BaseModel, ValidationError
from pydantic.functional_validators import AfterValidator
from typing import Any, List, AnyStr, Optional
from typing_extensions import Annotated


def check_type(mtype: str):
    assert mtype in ["efu_html", "poems", "efu_mob", "audio", "eor", "playlist20", "efu_html_mob", "audio_hls"]


MediaType = Annotated[AnyStr, AfterValidator(check_type)]


class TeplhodPublishMeta(BaseModel):
    code: AnyStr
    path: AnyStr
    content: MediaType


def validate(meta: dict) -> None:
    TeplhodPublishMeta(**meta)


class TeplohodMobEfuInternalMeta(BaseModel):
    code: AnyStr
    year: AnyStr
    title: AnyStr


class TeplohodEfuInternalMeta(BaseModel):
    code: AnyStr
    type: AnyStr
    content: AnyStr
    title: AnyStr
    annotation: Optional[AnyStr]
    authors: Optional[AnyStr]
    isbn: Optional[AnyStr]
    level_from: AnyStr
    level_to: AnyStr
    subject: AnyStr
    publisher: Optional[AnyStr]
    year: AnyStr
    forexpert: Optional[bool]
    fgos: Optional[bool]
    fpu: Optional[AnyStr]


class TeplohodAudiobookInternalMeta(BaseModel):
    code: AnyStr
    type: AnyStr
    content: AnyStr
    title: AnyStr
    annotation: Optional[AnyStr]
    authors: Optional[AnyStr]
    isbn: Optional[AnyStr]
    level_from: int
    level_to: int
    subject: AnyStr
    publisher: Optional[AnyStr]
    year: AnyStr


class TeplohodPoemInternalMeta(BaseModel):
    code: AnyStr
    type: AnyStr
    content: AnyStr
    title: AnyStr
    annotation: Optional[AnyStr]
    authors: Optional[AnyStr]
    level_from: AnyStr
    level_to: AnyStr
    subject: AnyStr
    publisher: Optional[AnyStr]
    year: AnyStr
    forexpert: Optional[bool]


class TeplohodPlaylistInternalMeta(BaseModel):
    code: AnyStr
    type: AnyStr
    content: AnyStr
    title: AnyStr
    annotation: Optional[AnyStr]
    authors: Optional[AnyStr]
    isbn: Optional[AnyStr]
    level_from: int
    level_to: int
    subject: AnyStr
    publisher: Optional[AnyStr]
    year: AnyStr
    forexpert: Optional[bool]
    start_file: AnyStr
