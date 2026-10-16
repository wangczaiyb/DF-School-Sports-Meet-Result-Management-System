"""学号固定8位数字，前两位表示年级（24表示24级），保留前导零。"""
import re
from typing import Annotated

from pydantic import AfterValidator, Field


STUDENT_NUMBER_ERROR = "学号必须为8位数字"


def is_valid_student_number(value: str) -> bool:
    return re.fullmatch(r"[0-9]{8}", value) is not None


def validate_student_number(value: str) -> str:
    value = value.strip()
    if not is_valid_student_number(value):
        raise ValueError(STUDENT_NUMBER_ERROR)
    return value


StudentNumber = Annotated[
    str,
    AfterValidator(validate_student_number),
    Field(description="8位数字学号，前两位表示年级，例如24000001表示24级"),
]
