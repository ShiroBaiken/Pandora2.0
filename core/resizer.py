import datetime
from io import BytesIO

from PIL import Image

from Bot.P_Files import FileType as ftype


class PhotoResise:
    """
    Simple class for resizing images.

    - file_type (str): The type of file being resized. Must be one of the FileType enum values.
    - file (BytesIO): The file to be resized, passed in as a BytesIO object.
    - size (tuple[int]): A tuple representing the dimensions of the passed image, in pixels.

    """

    def __init__(self, file_type: str, file: BytesIO, size: tuple[int]):
        self.file_type = file_type
        self.file = file
        self.size = size

    def resize(self) -> Image:
        """
        Resize the image to the half of initial size if any dimension > 500 pixels.

        :returns: Image: A PIL Image object representing the resized image.
        """
        img = Image.open(self.file)
        if self.file_type != ftype.PHOTO.value and max(self.size) < 500:
            return img
        new_size = tuple(int(x / 2) for x in self.size)
        return img.resize(new_size)

    @staticmethod
    def save(file) -> str:
        """
        Save the resized image to disk.
        :return: path to saved image as str
        """
        src = new_src = "I:/BrokenNest/{}.jpg".format(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
        file.save(new_src, 'JPEG')
        return src

    def resize_and_save(self) -> str:
        """
        Resize the image and save it to disk.
        :return: path to saved image as str
        """
        resized_img = self.resize()
        return self.save(resized_img)
