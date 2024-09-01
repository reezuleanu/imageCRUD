from pydantic import BaseModel, field_validator


class ModifyForm(BaseModel):
    """Model for http request body for modifying a picture,
    all attributes are optional"""

    # for resizing
    width: int = None  # width in pixels
    height: int = None  # height in pixels

    # for rotating
    rotate: float = None  # rotation in degrees

    # ai upscale
    upscale: int = None  # upscale factor (2, 3 or 4)

    # use gaussian blur
    blur: int = (
        None  # blur amount (it gets converted to an absolute value by Pillow anyway)
    )

    # sharpen
    sharpen: bool = False  # apply sharpen filter

    # grayscale
    grayscale: bool = False  # grayscale

    @field_validator("width", "height")
    @classmethod
    def validate_resolution(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Resolution scales must be higher than 0")

        return v

    @field_validator("rotate")
    @classmethod
    def validate_rotation(cls, v: float) -> float:
        if v <= 0 or v > 360:
            raise ValueError("Rotation degrees must be between 0 and 360")

        return v

    @field_validator("upscale")
    @classmethod
    def validate_upscale_factor(cls, v: int) -> int:
        return v
