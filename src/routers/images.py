from fastapi import APIRouter, HTTPException, Response, Body, UploadFile
from pymongo.errors import ServerSelectionTimeoutError
from mongoengine import ValidationError
from PIL import Image as Img
import os
import json
from database import Image
from utils import is_image

router = APIRouter(prefix="/images")


@router.get("/hello")
def hello() -> dict:
    """Hello world test endpoint

    Returns:
        dict: JSON response
    """
    return {"detail": "Hi there"}


@router.get("/")
def get_all_images() -> list[str]:
    """Get a list of all the image IDs in the database

    Returns:
        list[str]: list of image IDs
    """
    ids = []
    try:
        for image in Image.objects:
            ids.append(str(image.id))
    except ServerSelectionTimeoutError:
        raise HTTPException(500, "Database error")

    return ids


@router.get("/{image_id}")
def get_image(image_id: str) -> Response:
    """Get image from storage (used in browser)

    Args:
        image_id (int): id of the image

    Returns:
        Response: HTML response
    """
    try:
        image = Image.objects(id=image_id).first()
    except ValidationError:
        raise HTTPException(400, "Invalid image id")
    if image is None:
        raise HTTPException(404, "Image not found")

    # process image data
    data = json.loads(image.to_json())
    data["id"] = str(data["_id"]["$oid"])
    del data["_id"]
    data["size"] = f'{data["size"]} MB'

    # return HTML with data and the image
    return Response(
        f"""
        <html>
            <head>
                <title>Image with Text</title>
            </head>
            <body>
                {data}
                <img src="/static/{image_id}.{image.format}">
            </body>
        </html>
        """
    )


@router.post("/")
def post_image(image: UploadFile) -> dict:

    name = image.filename.lower()
    extension = name.split(".")[-1]

    # check file format
    is_image(extension)

    # open image with Pillow
    try:
        loaded_image = Img.open(image.file)
    except Img.UnidentifiedImageError:
        raise HTTPException(500, "Image could not be loaded and might be corrupted")

    # replace filename extension with file format extension, in case
    # there was a mismatch
    extension = loaded_image.format.lower()

    # check file format again
    is_image(extension)

    size = image.size * 0.000001  # size in MB

    image_data = {
        "size": size,
        "format": extension,
        "width": loaded_image.width,
        "height": loaded_image.height,
    }

    # save image info in database (without path)
    try:
        dbimage = Image(**image_data)
        dbimage.save()
        id = dbimage.id
    except Exception as e:
        raise HTTPException(500, str(e))

    # save file in storage and update path in DB
    try:
        loaded_image.save(f"storage/{id}.{extension}")
        loaded_image.close()
    except IOError:
        image.delete()
        raise HTTPException(500, "File could not be saved")

    dbimage.path = f"storage/{id}.{extension}"
    dbimage.save()

    return {
        "size": size,
        "name": image.filename,
        "format": extension,
        "width": loaded_image.width,
        "height": loaded_image.height,
        "path": dbimage.path,
    }


@router.delete("/{image_id}")
def delete_image(image_id: str) -> dict:
    """Delete an image to the server

    Args:
        image_id (int): image id

    Returns:
        dict: JSON response
    """

    try:
        image = Image.objects(id=image_id).first()

        if image is None:
            raise HTTPException(404, "Image does not exist")

        # delete image in storage
        if os.path.exists(image.path):
            os.remove(image.path)

        # delete image data form database
        image.delete()

    except ValidationError:
        raise HTTPException(400, "Invalid Image ID")

    return {"detail": "Image deleted successfully"}


@router.put("/{image_id}")
def modify_image(image_id: str, modifications: dict = Body()) -> dict:
    """Modify an image on the server

    Args:
        image_id (str): id of the image
        modifications (dict): modifications represented as JSON

    Returns:
        dict: JSON response
    """

    raise HTTPException(501)


@router.put("/replace/{image_id}")
def replace_image(image_id: str, new_image: UploadFile) -> dict:
    """Replace an image in the database, overwritting everything about it

    Args:
        image_id (str): id of image to be replaced
        new_image (UploadFile): new image

    Returns:
        dict: JSON response
    """
    image = new_image
    name = image.filename.lower()
    extension = name.split(".")[-1]

    # check file format
    is_image(extension)

    # open image with Pillow
    try:
        loaded_image = Img.open(image.file)
    except Img.UnidentifiedImageError:
        raise HTTPException(500, "Image could not be loaded and might be corrupted")

    # replace filename extension with file format extension, in case
    # there was a mismatch
    extension = loaded_image.format.lower()

    # check file format again
    is_image(extension)

    size = image.size * 0.000001  # size in MB

    dbimage = Image.objects(id=image_id).first()
    if dbimage is None:
        raise HTTPException(404, "Image not found")

    # replace image in storage
    try:
        loaded_image.save(dbimage.path)
        loaded_image.close()
    except IOError:
        raise HTTPException(500, "File could not be replaced")

    # replace image info in database
    dbimage.update(
        set__size=size,
        set__format=extension,
        set__width=loaded_image.width,
        set__height=loaded_image.height,
    )
    dbimage.save()

    return {
        "size": size,
        "name": image.filename,
        "format": extension,
        "width": loaded_image.width,
        "height": loaded_image.height,
        "path": dbimage.path,
    }
