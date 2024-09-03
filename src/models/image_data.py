from pydantic import BaseModel


class ImageData(BaseModel):
    """Dataclass for data about the image, used when writting and reading
    from database"""

    id: str = None
    size: float
    width: int
    height: int
    format: str
    path: str = None
