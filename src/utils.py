from fastapi import HTTPException


def is_image(extension: str) -> None:
    """Method to quickly check if the image format is accepted

    Args:
        image (UploadFile): image uploaded to fastapi
    """

    accepted_formats = ("png", "jpg", "jpeg")

    if extension not in accepted_formats:
        raise HTTPException(400, "This file format is not accepted")
