from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO

import motor.motor_asyncio as async_motor
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineQueryResultCachedPhoto, \
    InlineQueryResultCachedGif, InlineQueryResultCachedVideo, InlineQuery, InlineQueryResult

from Bot.bot_functions import Pandora
from Bot.FSM_manager import FSMManager
from Bot.P_Files import FileType
from Bot.P_states import NormalCall
from Bot.keyboards.likes_keyboards import LikeKeyboard
from core.resizer import PhotoResise
from core.string_collector import StringCollector


client = async_motor.AsyncIOMotorClient('localhost', 27017)
db = client['BrokenNest']
stored_posts = db.posts


class PrepareResize:
    """Class for retrieve information, necessary to repost file via inline telegram API methods,
    from incoming callback and data in aiogram storage"""
    def __init__(self, proxy_data, bot, fbytes=None, size=None, file_type=None):
        self.proxy_data: dict = proxy_data
        self.bot: Pandora = bot
        self.fbytes: BytesIO = fbytes
        self.size: tuple = size
        self.file_type = file_type

    async def download_by_id(self, file_info, file_type) -> BytesIO:
        """downloads temp file from telegram to store resized version of it"""
        if file_type != FileType.PHOTO.value:
            file_id = file_info['prewiew_id']
        else:
            file_id = file_info['file_id']
        prepared = await self.bot.get_file(file_id=file_id)
        downloaded = await self.bot.download_file(file_path=prepared.file_path)
        return downloaded

    async def build_resize_info(self) -> tuple[int, BytesIO, tuple]:
        """Gather necessary args for resizing from aiogram storage"""
        file_info = self.proxy_data['NormalCall:waiting_for_pic']
        self.size = file_info['size']
        self.file_type = file_info['file_type']
        self.fbytes = await self.download_by_id(file_info, self.file_type)
        return self.file_type, self.fbytes, self.size


class InlineQueryResultGenerator:
    inline_cash_args = ['file_type', 'file_id', 'caption', 'reply_markup']

    def __init__(self, values_list, inline_method=None):
        for arg_name in self.inline_cash_args:
            setattr(self, arg_name, values_list[self.inline_cash_args.index(arg_name)])
        self.parse_mode = 'html'
        self.inline_method = inline_method
        self.additional_kwargs = {}

    def generate_inline_cash(self) -> InlineQueryResult:
        """applyes chosen inline method for create inline cash"""
        return self.inline_method(id=1, caption=self.caption, parse_mode=self.parse_mode,
                                  reply_markup=self.reply_markup, **self.additional_kwargs)

    def assign_inline_method(self) -> None:
        """asociattes inline method with filetype in storage"""
        if self.file_type == FileType.PHOTO.value:
            self.inline_method = InlineQueryResultCachedPhoto
            self.additional_kwargs = {'photo_file_id': self.file_id}
        elif self.file_type == FileType.VIDEO.value:
            self.inline_method = InlineQueryResultCachedVideo
            self.additional_kwargs = {'video_file_id': self.file_id, 'title': 'a_c_video'}
        elif self.file_type == FileType.ANIMATION.value:
            self.inline_method = InlineQueryResultCachedGif
            self.additional_kwargs = {'gif_file_id': self.file_id}


@dataclass
class InlineQueryParser:
    """class to retrive various parameters for reposting from database and callback"""
    args_for_result_generator = ['file_type', 'file_id', 'message_caption', 'reply_markup']
    inline_query: InlineQuery
    state: FSMContext
    query_id: str = field(default=None)
    markup_type: str = field(default=None)

    def __post_init__(self):
        for attr_name in self.args_for_result_generator:
            setattr(self, attr_name, None)

    def get_keyboard_type(self) -> str:
        """Sets markup type (2 or 3 like buttons keyboard) based on data in callback"""
        self.markup_type = self.inline_query.query.rsplit(':', maxsplit=1)[1]
        return self.markup_type

    def get_query_id(self) -> str:
        """parse query id from callback data"""
        self.query_id = self.inline_query.query.rsplit(':', maxsplit=2)[1]
        return self.query_id

    def get_caption_from_proxy(self, proxy_data: dict) -> str | None:
        """
        Chose to get value of 'current_capture' key in aiogram storage or not.

        :param proxy_data: aiogram storage
        :return: If markup type != '2' or on failure returns None. Else returns value of
                'current_capture' key
        """
        if 'current_capture' not in proxy_data or self.markup_type == '2':
            return None
        capture_to_convert = proxy_data['current_capture']
        if self.markup_type != '2':
            return StringCollector(capture_to_convert).to_string()

    @staticmethod
    def get_file_id_from_proxy(proxy_data: dict) -> str:
        """method equal to shortcut to file_id in storage"""
        return proxy_data['NormalCall:waiting_for_pic']['file_id']

    @staticmethod
    def get_file_type_from_proxy(proxy_data: dict) -> int:
        """method equal to shortcut to filetype in storage"""
        return proxy_data['NormalCall:waiting_for_pic']['file_type']

    async def get_values_from_proxy(self) -> None:
        """Gets 'file_type' 'message_caption' and 'file_id' values from storage"""
        async with self.state.proxy() as data:
            self.file_type = self.get_file_type_from_proxy(data)
            self.message_caption = self.get_caption_from_proxy(data)
            self.file_id = self.get_file_id_from_proxy(data)

    def chose_reply_markup(self, posts_id) -> None:
        """creates corresponding 'ReplyMarkup' object"""
        likes_markup = LikeKeyboard()
        match self.markup_type:
            case '1':
                self.reply_markup = likes_markup.create_new_markup_with_two_reactions(posts_id)
            case '2':
                self.reply_markup = likes_markup.create_new_markup_with_three_reactions(posts_id)
            case _:
                pass

    def summary_for_query_generator(self, new_post_id) -> list:
        """Compresses values from storage to list"""
        self.chose_reply_markup(new_post_id)
        return [getattr(self, x) for x in self.args_for_result_generator]

    async def get_basic_info_from_query(self) -> None:
        """Parses callback query for repost data"""
        self.get_keyboard_type()
        self.get_query_id()
        await self.get_values_from_proxy()


class RepostToChannel:
    """Class to buid chosen InlineQuery object and create new post in channel with it"""
    post_sample = {  # basic structure of data saved to Mongo storage about new crated post
        "id": '',
        "src": '',
        "photo": '',
        "width": '',
        "height": '',
        "users_who_like": '',
        "users_who_dislike": '',
    }

    def __init__(self, state, inline_query, bot, manager=None):
        self.inline_query = inline_query
        self.state: FSMContext = state
        self.bot: Pandora = bot
        self.manager: FSMManager = manager
        self.posts = stored_posts
        self.query_parser = InlineQueryParser(self.inline_query, self.state)

    def save_file_info_to_buffer(self, file_info: list) -> None:
        """Matches keys from post_sample with certain ordered list of values, and saves result at buffer"""
        dict_slice = [x for x in self.post_sample][:5]
        self.manager.buffer.update(
            zip(dict_slice, file_info)
        )

    def like_keyboards_key_update_for_two_buttons_like_keyboard(self) -> None:
        """Creates in buffer info about keyboard, attached to new post"""
        missing_keys = [x for x in self.post_sample][5:]
        self.manager.buffer.update(dict.fromkeys(missing_keys, ['']))

    def like_keyboards_key_update_for_three_buttons_like_keyboard(self) -> None:
        """adds missing keys for attached to new post keyboard with 3 buttons"""
        self.like_keyboards_key_update_for_two_buttons_like_keyboard()
        missing_keys = {
            'users_who_fine': [''],
            "users_who_disgust": ['']

        }
        del self.manager.buffer["users_who_dislike"]
        self.manager.buffer.update(missing_keys)

    def add_keyboard_info(self, keyboard_type: str) -> None:
        """
        Adds keys for attachet to post keyboards into buffer, depends on keyboard type from callback
        """
        match keyboard_type:
            case '1':
                self.like_keyboards_key_update_for_two_buttons_like_keyboard()
            case '2':
                self.like_keyboards_key_update_for_three_buttons_like_keyboard()
            case _:
                pass

    def file_info_to_list(self, file_info_from_preparer: tuple, path: str) -> list:
        """
        Converts values to list with certain order, to match them with post_sample keys
        """
        info = [self.manager.data_storage['NormalCall:waiting_for_pic']['message_id'], path,
                self.manager.data_storage['NormalCall:waiting_for_pic']['file_id'], file_info_from_preparer[2][0],
                file_info_from_preparer[2][1]]
        return info

    async def prepare_file_info_save(self) -> None:
        """
        Gathers all data for creating new post and such as file size, file id, etc.
        Creates resized kopy of file locally.
        Saves gathered data to buffer.
        :return: None
        """
        self.manager = FSMManager(self.state)
        await self.manager.get_current_data()
        resize_preparer = PrepareResize(self.manager.data_storage, self.bot)
        file_info = await resize_preparer.build_resize_info()
        resizer = PhotoResise(*file_info)
        saved_thumbnail_src = resizer.resize_and_save()
        prepared_for_compression = self.file_info_to_list(file_info, saved_thumbnail_src)
        self.save_file_info_to_buffer(prepared_for_compression)

    async def write_file_as_posted(self) -> str:
        """
        Creates new record in collection of posts in database
        :return: On succes, returns id of new record
        """
        insertion = await self.posts.insert_one(self.manager.buffer)
        return insertion.inserted_id

    async def create_post(self) -> None:
        """
        Perform repost to another chat with recording with data retention in database.
        Cleans FSMManager buffer.
        Sets bot in waiting_for_pic state
        :return: None
        """
        await self.prepare_file_info_save()
        await self.query_parser.get_basic_info_from_query()
        self.add_keyboard_info(self.query_parser.markup_type)
        new_post_id = await self.write_file_as_posted()
        summary_for_inline_result = self.query_parser.summary_for_query_generator(new_post_id)
        query_result_generator = InlineQueryResultGenerator(summary_for_inline_result)
        query_result_generator.assign_inline_method()
        query_result = query_result_generator.generate_inline_cash()
        await self.bot.answer_inline_query(self.inline_query.id, [query_result])
        await self.manager.flush()
        await NormalCall.waiting_for_pic.set()
