from fastapi import HTTPException
from PIL import Image, ImageFilter
from PIL.ImageFile import ImageFile
from super_image import EdsrModel, ImageLoader
from torchvision.transforms.functional import to_pil_image


def is_image(extension: str) -> None:
    """Method to quickly check if the image format is accepted

    Args:
        image (UploadFile): image uploaded to fastapi
    """

    accepted_formats = ("png", "jpg", "jpeg")

    if extension not in accepted_formats:
        raise HTTPException(400, "This file format is not accepted")


# ! ONLY SUPPORTS x2
def upscale(image: ImageFile, factor: int) -> ImageFile:
    """Upscale an image with AI by a factor of 2, 3 or 4

    Args:
        image (ImageFile): image to upscale
        factor (int): upscale factor

    Returns:
        ImageFile: upscaled image
    """

    model = EdsrModel.from_pretrained("eugenesiow/edsr-base", scale=factor)
    inputs = ImageLoader.load_image(image)
    preds = model(inputs)
    preds = preds.squeeze(0)
    return to_pil_image(preds)

    ImageLoader.save_image(preds, "./scaled_2x.png")
    ImageLoader.save_compare(inputs, preds, "./scaled_2x_compare.png")


def apply_modifications(image_path: str, json: dict) -> ImageFile:
    """Apply all changes to an image, then return it

    Args:
        json (dict): dictionary with all the modification details
    """
    try:
        image = Image.open(image_path)
    except IOError:
        return None

    allowed_modification_options = {
        "width": lambda x: image.resize((x, image.height)),
        "height": lambda y: image.resize((image.width, y)),
        "rotate": lambda x: image.rotate(x),
        "upscale": lambda _: upscale(image, 2),
        "blur": lambda x: image.filter(ImageFilter.GaussianBlur(x)),
        "sharpen": lambda _: image.filter(ImageFilter.SHARPEN),
        "grayscale": lambda _: image.convert("L"),
    }

    for key in json:
        if key in allowed_modification_options and json[key] not in (False, None):
            image = allowed_modification_options[key](json[key])

    return image
