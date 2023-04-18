import typing
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from typing import Union

from aiogram.types import Message

from Bot.bot_functions import Pandora
from image_check import is_pic_already_posted_check

""" This code is designed to provide a flexible and extensible framework 
for working with different types of files in a chatbot, 
allowing the bot to easily manage and store information about the files it receives.
"""


class FileType(Enum):
    """
    represents type of incoming file to manage differences in types handling
    """
    PHOTO = 1
    ANIMATION = 2
    VIDEO = 3


@dataclass
class BotFile:
    """
    Represents a file bot currently works with

    - from_user: id of user, which send file to bot
    - file_type: the type of file (always FileType.PHOTO)
    - message_id: id of incoming message with file
    - file_id: id of incoming file
    - prewiew_id: id of file prewiew
    - size: width and height of file in tuple
    - src: path to locally saved temporary copy
    - file_type_value: the integer value of the file type (always 1)
    - bytes: BytesIO object of file
    """
    from_user: typing.Optional[str] = None
    file_type: FileType = FileType.PHOTO
    message_id: typing.Optional[str] = None
    file_id: typing.Optional[str] = None
    prewiew_id: typing.Optional[str] = None
    size: typing.Optional[tuple] = None
    src: typing.Optional[str] = None
    file_type_value = 1
    bytes: bytes = field(init=False)

    def dict_format(self) -> dict:
        """wraps file info to prepare it be stored in bd"""
        to_buffer = {'file_type': self.file_type_value}
        to_buffer.update({key: val for key, val in self.__dict__.items()
                          if key != 'bytes' and key != 'file_type'})
        return to_buffer


@dataclass
class Animation(BotFile):
    """
    Represents an animation file.

    - animation_id: The ID of the animation file.
    - file_type: The type of file (always FileType.ANIMATION).
    - file_type_value: The integer value of the file type (always 2).

    """
    animation_id: typing.Optional[str] = None
    file_type = FileType.ANIMATION
    file_type_value = 2


@dataclass
class Video(BotFile):
    """
       Represents an video file.

       - video_id: The ID of the animation file.
       - file_type: The type of file (always FileType.VIDEO).
       - file_type_value: The integer value of the file type (always 3).

       """
    video_id: typing.Optional[str] = None
    file_type = FileType.VIDEO
    file_type_value = 3


class FileFactory:
    """
    A factory for creating BotFiles.

    :atributes:
    - message: The message containing the file.

    """

    def __init__(self, message: Message):
        self.message: Message = message
        self.file = BotFile()

    def get_basic_file_info(self) -> None:
        """
        stores user id and message id in corresponding file object
        """
        self.file.from_user = self.message.from_user.id
        self.file.message_id = self.message.message_id

    def gather_info(self) -> None:
        """
        basic method to store paramethers into corresponding file object
        :return:
        """
        self.get_basic_file_info()

    def build(self) -> BotFile:
        """returns corresponding object"""
        return self.file

    @property
    def download_id(self):
        """property, which returns id of file, which must be downloaded for sample save and comparing"""
        return self.file.id


class PhotoFileFactory(FileFactory):
    """
    The PhotoFileFactory class is a factory class that is used to create and manage BotFile objects (which provides
    all necessary methods to handle photo files).
    It inherits from the FileFactory class, which provides basic functionality for gathering information about files.
    """

    def __init__(self, message: Message):
        super().__init__(message)
        self.file = BotFile()

    @property
    def photo(self) -> BotFile:
        """A read-write property that returns the Photo object associated with this factory"""
        return self.file

    @photo.setter
    def photo(self, value: BotFile) -> None:
        self.file = value

    def get_photo_size(self) -> None:
        """stores width and height of photo in associated Photo object"""
        self.photo.size = (self.message.photo[-1].width, self.message.photo[-1].height)

    def get_photo_id(self) -> None:
        """stores file id in class arg"""
        self.photo.file_id = self.message.photo[-1].file_id

    @property
    def download_id(self):
        """property, which returns id of file, which must be downloaded for sample save and comparing"""
        return self.photo.file_id

    def gather_info(self) -> None:
        """Gathers information about the photo, including its ID and thumbnail,
         and stores it in the associated Photo object."""
        self.get_photo_id()
        self.get_photo_size()
        super(PhotoFileFactory, self).gather_info()


class AnimationFileFactory(FileFactory):
    """
    The AnimatonFileFactory class is a factory class that is used to create and manage Animaton objects.
    It inherits from the FileFactory class, which provides basic functionality for gathering information about files.
    """

    def __init__(self, message):
        super().__init__(message)
        self.file = Animation()

    @property
    def animation(self) -> Animation:
        """
        A read-write property that returns the Animation object associated with this factory.
        """
        return self.file

    @animation.setter
    def animation(self, value: Animation) -> None:
        self.file = value

    def get_prewiew_size(self):
        """stores file size as tuple in class arg"""
        self.animation.size = (self.message.document.thumb.width,
                               self.message.document.thumb.height)
        return self

    def get_animation_prewiew_id(self) -> None:
        """stores file prewiew id in class arg"""
        self.animation.prewiew_id = self.message.document.thumb.file_id

    @property
    def download_id(self):
        """property, which returns id of file, which must be downloaded for sample save and comparing"""
        return self.animation.prewiew_id

    def get_animation_id(self) -> None:
        """stores file id in class arg"""
        self.animation.file_id = self.message.animation.file_id

    def gather_info(self) -> None:
        """
        Gathers information about the animation, including its ID and thumbnail,
        and stores it in the associated Animation object.
        :return: None
        """
        self.get_animation_prewiew_id()
        self.get_prewiew_size()
        self.get_animation_id()
        super(AnimationFileFactory, self).gather_info()


class VideoFileFactory(FileFactory):
    """
    The VideoFileFactory class is a factory class that is used to create and manage Video objects.
    """

    def __init__(self, message: Message):
        super().__init__(message)
        self.file = Video()

    @property
    def video(self) -> Video:
        """A read-write property that returns the Video object associated with this factory"""
        return self.file

    @video.setter
    def video(self, value: Video):
        self.file = value

    def get_prewiew_size(self):
        """
        Retrieves the size of the video's thumbnail and stores it in the size property of the associated Video object.
        """
        self.video.size = (self.message.video.thumb.width,
                           self.message.video.thumb.height)
        return self

    @property
    def download_id(self):
        return self.video.prewiew_id

    def get_video_prewiew_id(self) -> None:
        """
        Retrieves the ID of the video's thumbnail and stores it in
        the prewiew_id property of the associated Video object.
        """
        self.video.prewiew_id = self.message.video.thumb.file_id

    def get_video_id(self) -> None:
        """
        Retrieves the ID of the video and stores it in the file_id property of the associated Video object.
        """
        self.video.file_id = self.message.video.file_id

    def gather_info(self) -> None:
        """
         Gathers information about the video, including its ID and thumbnail,
         and stores it in the associated Video object.
        """
        self.get_video_prewiew_id()
        self.get_prewiew_size()
        self.get_video_id()
        super(VideoFileFactory, self).gather_info()


class TelegrammFileHandler:
    """Class to for creation of corresponding BotFile object, depending on incoming type of file and store
    information of incoming file in it."""
    def __init__(self, message: Message, bot: Pandora, file_type: typing.Optional[FileType] = None,
                 factory: typing.Optional[FileFactory] = None,
                 is_already_posted=False):
        self.message: Message = message
        self.file_type: FileType = file_type
        self.factory: FileFactory = factory
        self.is_already_posted: Union[str, bool] = is_already_posted
        self.alredy_posted_notice: str = 'Seems like you already posted this before'
        self.bot: Pandora = bot

    def file_type_assign(self):
        """assigns file type as FileType depends on keys in incoming message"""
        if 'animation' in self.message:
            self.file_type = FileType.ANIMATION
            self.factory = AnimationFileFactory(self.message)
        elif 'video' in self.message:
            self.file_type = FileType.VIDEO
            self.factory = VideoFileFactory(self.message)
        elif 'photo' in self.message:
            self.file_type = FileType.PHOTO
            self.factory = PhotoFileFactory(self.message)

    async def open_user_file(self, file_id: str) -> BytesIO:
        """returns file, send by user or its prewiew as Bytes IO object """
        prepared = await self.bot.get_file(file_id=file_id)
        downloaded = await self.bot.download_file(file_path=prepared.file_path)
        return downloaded

    async def prepare_file(self) -> None:
        """stores information about file into file object"""
        self.file_type_assign()
        self.factory.gather_info()
        self.factory.file.bytes = await self.open_user_file(self.factory.download_id)

    async def already_posted_check(self) -> None:
        """searching for similar images in saved thumbnails"""
        if check_result := is_pic_already_posted_check(self.factory.file.bytes):
            self.is_already_posted = check_result

    def aldeady_posted_reply(self) -> None:
        """returns result of searching for similar images in saved thumbnails in format of url to post"""
        already_posted_notice = self.alredy_posted_notice
        prefix_tuple = ('/brkennest/', '/c/1435716086/')
        if self.duplicate_url.isdigit():
            self.bot.send_message(
                chat_id=self.message['from']['id'],
                reply_to_message_id=self.duplicate_url,
                text=already_posted_notice
            )
        elif self.duplicate_url.startswith(prefix_tuple):
            reply = f'{already_posted_notice}\nhttps://t.me{self.duplicate_url}'
            self.bot.send_message(
                chat_id=self.message['from']['id'],
                reply_to_message_id=self.message.message_id,
                text=reply
            )
