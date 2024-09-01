from mongoengine import (
    connect,
    Document,
    FloatField,
    IntField,
    StringField,
)

db = connect("imageCRUD", serverSelectionTimeoutMS=2000)


class Image(Document):
    """MongoDB document holding image info and the path to it"""

    size = FloatField()  # size in MB
    width = IntField()  # width in pixels
    height = IntField()  # height in pixels
    format = StringField(max_length=10)  # image file format
    path = StringField(max_length=128)  # path to image in storage
