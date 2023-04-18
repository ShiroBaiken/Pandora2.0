from __future__ import annotations

from typing import Iterable, Coroutine

from aiogram import types
from aiogram.dispatcher import FSMContext

from bot_functions import Pandora
from Bot.FSM_manager import FSMManager
from Bot.P_Files import TelegrammFileHandler
from Bot.P_states import NormalCall
from Bot.keyboards import menu_keyboards
from core import exceptions
from core.reducer import ParsedInfoReducer
from core.reverse_image_search import search_for_sources
from core.string_collector import StringCollector
from core.tag_generator import TagGeneratorHandler
from parsers.imageboards_parsers import parse_imageboards
from parsers.validator import ReprForLinksSearch


# General structure of events happens:
# > user sends file
# > if file wasn't gif od mp4 revese search starts (1)
# >> parsing Sause Nao for links to imageboards with picture
# >> if Sause Nao search succed starts parsing imageboards (2)
# >> from imageboars getting tags
# >> tags from several imageboards united in one list
# >> converted to string and send to user as reply message
# Non-general cases:
# 1 file was gif or mp4 - user got message asking if user want search for sourses anyway
# 2 SauseNao search failed - selenium started, trying to get links to imageboards with yandex reverse search


class NewIncomingFile:
    """main handler of files incoming from user"""

    def __init__(self, bot: Pandora, message: types.Message | types.CallbackQuery, state, state_group=NormalCall,
                 manager=None, file_handler=None):
        self.state_group = state_group
        self.bot: Pandora = bot
        self.message: types.Message = message
        self.state: FSMContext = state
        self.manager: FSMManager = manager
        self.file_handler = file_handler

    async def process_preliminary_file_handle(self, message):
        """creates TelegrammFileHandler instance and assigns its args by data from message"""
        self.file_handler = TelegrammFileHandler(message, self.bot)
        await self.file_handler.prepare_file()

    async def self_posted_check(self):
        """raises exception if sample of inconing picture
         stored in db, else saves file data"""
        await self.file_handler.already_posted_check()
        if self.file_handler.is_already_posted is not False:
            raise exceptions.PictureAlreadyPosted(self.file_handler.is_already_posted)
        await self.manager.save_to_proxy()

    def process_reverse_search(self) -> tuple[dict, Iterable[str | None]]:
        """passes bytes of incoming file or its prewiew to reverse search SauceNAO parser
        in core.reverse_image_search"""
        links, artist = search_for_sources(self.file_handler.factory.file.bytes.getvalue(), self.bot.yandex_parser)
        # somehow BytesIO from aiogram doesent reads be requests library methods with some types of previews
        # as it is. Adding getvalue() to BytesIO fixes this
        return links, artist

    async def source_found_reply(self) -> None:
        """sends user notification of reverse image search succed as message"""
        user_id = None
        if type(self.message) == types.Message:
            user_id = self.message.from_user.id
        else:
            if 'message' not in self.message:
                user_id = self.message.callback_query['from'].id
            elif 'callback_query' not in self.message:
                if not (user_id := dict(self.message['message']).get('chat').get('id')):
                    user_id = self.message['from'].id
        await self.bot.send_message(user_id, 'souce found!')

    async def gather_info_from_imageboards(self, search_result: dict, artists_result: Iterable[str | None]) -> dict:
        """parse imageboard for picture descriptions tags with parsers.imageboards_parsers"""
        pre_reduced = await parse_imageboards(search_result)
        pre_reduced['artist'].append(artists_result)
        if not any([x for x in pre_reduced['tags'] if x != ['']]):
            raise exceptions.UnsuccefulParsing
        await self.state_group.next()
        return pre_reduced

    async def process_reduce(self, pic_parsed_info: dict) -> dict:
        """shrincs parsed tags in flat lists of categhories"""
        await self.state_group.next()
        red = ParsedInfoReducer()
        return red.reduce_all(pic_parsed_info)

    async def generate_hashtags(self, pic_parsed_info) -> dict:
        """transform reduced tags into telegramm's hastags using bot's db"""
        tag_gen = TagGeneratorHandler(parsed_tags=pic_parsed_info, filter_value='standart')
        await self.state_group.next()
        return tag_gen.recognize_and_generate_hasttags()

    @staticmethod
    def generate_capture(generated_hastags: dict) -> str:
        """converts capture dict to string"""
        return StringCollector(generated_hastags).to_string()

    async def set_redirection_flag(self) -> None:
        """adds redirection flag to storage for search with yandex"""
        self.manager = FSMManager(self.state)
        self.manager.save_to_buffer({'redirection_flag': True})
        await self.manager.save_to_proxy()

    async def prepare_file(self):
        """inits FSMManager, get gata from storage, get filedata from message"""
        self.manager = FSMManager(self.state)
        await self.manager.get_current_data()
        await self.process_preliminary_file_handle(self.message)

    @staticmethod
    def parsed_links_check(links_to_pic: dict) -> str | bool:
        """return False if not only unparsable imageboards was in SauseNAO reverse search result
        else return str repr of links to unparseble imageboards"""
        str_checker = ReprForLinksSearch(links_to_pic)
        str_of_parsed = str_checker.str_repr_for_parsed_links()
        if str_of_parsed:
            return str_of_parsed
        else:
            return False

    async def already_posted_check(self):
        await self.self_posted_check()

    async def save_prepared_file(self):
        """stores file data ftom FileHandler in buffer and aiogram storage"""
        await self.manager.save_to_buffer_under_state_key(
            self.file_handler.factory.file.dict_format())
        await self.manager.save_to_proxy()

    async def reverse_search(self) -> tuple[dict, Iterable[str | None]]:
        """performs reverise image search with parsers.sause_nao_operations"""
        self.carnaval_flag()  # if flag is set, rises error and skips reverse search part
        links_to_user_picture, artists = self.process_reverse_search()
        await self.state_group.next()
        return links_to_user_picture, artists

    async def save_reverse_search(self, links_to_user_picture) -> Coroutine:
        """saves parsed links of user file from SauseNao"""
        await self.manager.save_to_buffer_under_state_key(links_to_user_picture)

    async def parse_and_save_tags(self, links_to_picture, artists) -> dict:
        """parses imageboards for description tags, saves result to buffer"""
        pic_desc = await self.gather_info_from_imageboards(links_to_picture, artists)
        await self.manager.save_to_buffer_under_state_key(pic_desc)  # point of saving it to buffer is what proxy can be
        # disconnected and parsing imagegeboards will fail. So dont saving this result to proxy can possibly allow
        # to resume search without consuming extra request to Souse Nao.  However methods for resume
        # search not implemented yet
        return pic_desc

    def carnaval_flag(self):
        """checks manually seted switch for error rise"""
        if 'ac_flag' in self.manager.data_storage:
            raise exceptions.ApplyThreeReactionsKeyboard

    def sfw_flag(self, generated_tags):  #
        """adds special tag in parsed tags if manual flag is set"""
        if 'sfw_flag' in self.manager.data_storage:
            generated_tags['tags'].append('#sfw')

    async def reduce_and_save_parsed_tags(self, pic_desc: dict) -> dict:
        """flatten lists of parsed tags and saves result to buffer"""
        reduced_pic_desc = await self.process_reduce(pic_desc)
        await self.manager.save_to_buffer_under_state_key(reduced_pic_desc)
        return reduced_pic_desc

    async def generate_hashtags_from_tags(self, reduced_pic_desc: dict):
        """converts parsed tags to telegram hashtags and saves them to buffer and aiogram storage.
        \nadds 'history' field to storage
        \nthis method contain 'sfw_flag_check' """
        hashtags = await self.generate_hashtags(reduced_pic_desc)
        self.sfw_flag(hashtags)
        await self.manager.save_tags_under_state_name_key(hashtags)
        self.manager.update_history_manager()
        await self.manager.history_manager.start_history(self.state)
        self.manager.update_last_capture(hashtags)
        return hashtags

    async def reply_generated_capture_to_file(self, hashtags: dict):
        """converts hashtags to string and sends in to user as message"""
        capture = self.generate_capture(hashtags)
        await self.message.reply(capture, reply_markup=menu_keyboards.confirm_keyboard)

    async def yandex_redirected_search(self) -> dict:
        """gets links to user file with selenium"""
        self.manager = FSMManager(self.state)
        await self.manager.get_current_data()
        if self.bot.yandex_parser.browser is None:
            self.bot.yandex_parser.create_browser()
        self.bot.yandex_parser.full_parcing_cycle()
        return self.bot.yandex_parser.parser.parsed_links

    async def from_link_to_capture_process(self, links_to_picture: dict, artists: Iterable[str | None]) -> str:
        """steps from links to user file was get to sending user message with capture string. Same for both cases of
        parsing links"""
        is_only_not_parseble_imageboards = self.parsed_links_check(links_to_picture)
        if is_only_not_parseble_imageboards:
            return is_only_not_parseble_imageboards
        await self.source_found_reply()
        parsed_tags_from_imageboards = await self.parse_and_save_tags(links_to_picture, artists)
        reduced_parsed_tags = await self.reduce_and_save_parsed_tags(parsed_tags_from_imageboards)
        capture_hasthags = await self.generate_hashtags_from_tags(reduced_parsed_tags)
        await self.manager.save_to_proxy()
        capture = self.generate_capture(capture_hasthags)
        return capture

    async def resume_reverse_search_for_prepared_file(self):
        """case if parsing didnt was initiated as reply for user file"""
        self.manager = FSMManager(self.state)
        await self.manager.get_current_data()
        self.file_handler = TelegrammFileHandler(message=self.message.message.reply_to_message,
                                                 bot=self.bot)
        await self.file_handler.prepare_file()
        links, artists = await self.reverse_search()
        capture = await self.from_link_to_capture_process(links, artists)
        await self.manager.save_to_proxy()
        await self.bot.edit_bot_reply_text(self.message, text=capture,
                                           reply_markup=menu_keyboards.confirm_keyboard)
