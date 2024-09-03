from fastapi import APIRouter, HTTPException, Response, Body, UploadFile
from pymongo.errors import ServerSelectionTimeoutError
from mongoengine import ValidationError
from PIL import Image as Img
import os
import json

from database import Image
from models import ModifyForm, ImageData
from utils import is_image, apply_modifications
from producer import rabbit_logging

router = APIRouter(prefix="/images")


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
        rabbit_logging(
            "logging.database", "ERROR: Could not read image ids from database"
        )
        raise HTTPException(500, "Database error")

    # rabbit_logging("logging.database", "INFO: Read image ids from database")
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
        if image is None:
            raise HTTPException(404, "Image not found")
    except ValidationError:
        raise HTTPException(400, "Invalid image id")

    try:
        # validate and process image data
        data = json.loads(image.to_json())
        data["id"] = str(data["_id"]["$oid"])
        del data["_id"]
        # data["size"] = f'{data["size"]} MB'
        data = ImageData.model_validate(data)
    except ValueError:
        rabbit_logging("logging.database", "ERROR: Image has invalid metadata")
        raise HTTPException(400, "Image has invalid metadata")
    except Exception as e:
        rabbit_logging(
            "logging.database", "ERROR: Image could not be fetched, reason: " + str(e)
        )
        raise HTTPException(500, "Image could not be fetched, reason: " + str(e))

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
    """Post image to database and server sotrage

    Args:
        image (UploadFile): image uploaded

    Returns:
        dict: JSON response
    """

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

    # validate image data
    try:
        data = ImageData(
            size=size,
            format=extension,
            width=loaded_image.width,
            height=loaded_image.height,
        )
    except ValueError:
        rabbit_logging("logging.database", "ERROR: Image has invalid metadata")
        raise HTTPException(400, "Image has invalid metadata")
    except Exception as e:
        rabbit_logging(
            "logging.database", "ERROR: Image could not be uploaded, reason: " + str(e)
        )
        raise HTTPException(500, "Image could not be uploaded, reason: " + str(e))

    # save image in storage and in database
    try:
        dbimage = Image(**data.model_dump())
        dbimage.save()
        id = dbimage.id

        # save file in storage and update path in DB
        loaded_image.save(f"storage/{id}.{extension}")
        loaded_image.close()
        dbimage.path = f"storage/{id}.{extension}"
        data = ImageData.model_validate_json(dbimage.to_json())
        dbimage.save()

        # set id for pydantic object
        data.id = str(id)

    except Exception as e:
        os.remove(f"storage/{dbimage.id}.{extension}")
        dbimage.delete()
        rabbit_logging(
            "logging.database",
            "ERROR: Could not post image to database, reason: " + str(e),
        )
        raise HTTPException(500, "File could not be saved")

    return data.model_dump()


@router.delete("/{image_id}")
def delete_image(image_id: str) -> dict:
    """Delete an image to the server

    Args:
        image_id (str): image id

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
    except Exception as e:
        rabbit_logging(
            "logging.database",
            "ERROR: Could not delete image from database, reason: " + str(e),
        )
        raise HTTPException(500, "Could not delete image from database")

    return {"detail": "Image deleted successfully"}


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

    # get previous image data from the database and validate it
    try:
        dbimage = Image.objects(id=image_id).first()
        if dbimage is None:
            raise HTTPException(404, "Image not found")

        ImageData.model_validate_json(dbimage.to_json())

    except ValidationError:
        raise HTTPException(400, "Invalid image id")
    except ValueError:
        rabbit_logging(
            "logging.database",
            f"CRITICAL: Invalid image data detected in database at {image_id}",
        )
        raise HTTPException(
            500,
            "Image previously had invalid data saved, therefore the operation was halted for investigation",
        )

    # update image data
    try:

        # validate new info
        data = ImageData(
            id=image_id,
            size=size,
            format=extension,
            width=loaded_image.width,
            height=loaded_image.height,
            path=f"storage/{image_id}.{extension}",
        )

        # replace image info in database
        dbimage.update(
            set__size=data.size,
            set__format=data.format,
            set__width=data.width,
            set__height=data.height,
            set__path=data.path,
        )

        dbimage.save()

        # replace image in storage
        loaded_image.save(data.path)
        loaded_image.close()

    except ValueError:
        rabbit_logging("logging.database", "ERROR: Image has invalid metadata")
        raise HTTPException(400, "Image has invalid metadata")

    except Exception as e:
        rabbit_logging(
            "logging.database", "ERROR: Could not update image data, reason: " + str(e)
        )
        raise HTTPException(500, "Could not update image data, reason: " + str(e))

    return data.model_dump()


# ! Some tomfoolery is going on here
@router.put("/{image_id}")
def modify_image(image_id: str, modifications: ModifyForm = Body()) -> dict:
    """Modify an image on the server

    Args:
        image_id (str): id of the image
        modifications (dict): modifications represented as JSON

    Returns:
        dict: JSON response
    """

    # convert to dict for iteration
    modifications = modifications.model_dump()

    # open image and process modifications using drastiq workers
    try:
        dbimage = Image.objects(id=image_id).first()
        image_path = dbimage.path
        if not os.path.isfile(image_path):
            raise Exception
    except ValidationError:
        raise HTTPException(400, "Invalid image id")
    except Exception as e:
        rabbit_logging(
            "logging.database",
            "ERROR: Could not find image on server, reason: " + str(e),
        )
        raise HTTPException(404, "Could not find image")

    # ! workers will do the changes, then write the image to disk, and return nothing
    message = apply_modifications.send(image_path, modifications)
    del message  # just so flake8 stops screaming at me
    # try:
    #     result = message.get_result(block=True)
    # except Exception as e:
    #     raise HTTPException(500, str(e))

    # reopen the image and update data in the database
    try:
        modified_image = Img.open(image_path)

        # update database details
        dbimage.update(
            set__size=os.path.getsize(image_path) * 0.000001,
            # set__format=modified_image.format.lower(),    # TODO figure out why this is NoneType
            set__width=modified_image.width,
            set__height=modified_image.height,
        )
        dbimage.save()
        modified_image.close()
        # rabbit_logging("logging.database", "INFO: Image data updated successfully")

    except Exception as e:
        rabbit_logging(
            "logging.database",
            "ERROR: Image data could not be updated, reason: " + str(e),
        )
        raise HTTPException(500, "Image data could not be updated")

    return {"detail": "Image modified successfully!"}
