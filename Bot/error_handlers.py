import selenium.common.exceptions
from aiogram import Dispatcher
from aiogram.types import Update

import core.exceptions as errors
from Bot.P_states import NormalCall
from Bot.bot_functions import Pandora
from Bot.keyboards import menu_keyboards
from Bot.keyboards.likes_keyboards import LikeKeyboard
from Bot.new_file_from_user import NewIncomingFile


class CustomErrorHandler:

    def __init__(self, update, dp, exc, bot):
        self.update: Update = update
        self.dispatcher: Dispatcher = dp
        self.exception: errors.CustomError = exc
        self.bot: Pandora = bot

    # aiogram's error handler catches 'update' instead of 'message' or 'callback'
    #  updates have a bit different map of keys
    def get_message_to_reply_id(self) -> str:
        """gets message id from update"""
        if 'message' not in self.update:
            return self.update.callback_query.message.reply_to_message.message_id
        elif 'callback_query' not in self.update:
            return self.update.message.message_id

    def get_user_to_reply_id(self) -> str:
        """gets userid from update"""
        if 'message' not in self.update:
            return self.update.callback_query['from'].id
        elif 'callback_query' not in self.update:
            return self.update.message.from_user.id

    async def anal_carnaval_error_reply(self) -> None:
        """this case triggered by core.content_filter and used to re-send user file back with reactions keyboard"""
        reply_markup_generator = LikeKeyboard()
        fake_likes_keyboard = reply_markup_generator.create_new_markup_with_three_reactions('0')
        # reaction keyboard muted in chat with bot
        ready_markup = reply_markup_generator.add_repost_button(fake_likes_keyboard, 2)
        reply_to = self.get_message_to_reply_id()
        user = self.get_user_to_reply_id()
        await self.bot.send_message(chat_id=user, text=f'{self.exception}', reply_to_message_id=reply_to,
                                    reply_markup=ready_markup)
        await NormalCall.posting.set()

    async def standart_error_reply(self):
        """returns error name and error message to user as telegramm mesage"""
        print('')  # logs
        print(self.exception)
        print('')
        reply_to = self.get_message_to_reply_id()
        user = self.get_user_to_reply_id()
        await self.bot.send_message(text=f'{type(self.exception).__name__}: {self.exception}',
                                    chat_id=user, reply_to_message_id=reply_to,
                                    reply_markup=menu_keyboards.confirm_keyboard)

    async def error_search_redirect(self):
        """starts search with Yendex reverse search engine.
        Process of reverse serch handled bu NewIncomingFile class.
        Sets redirectin flag in storage.
        \n sets bot into ForsedRedirect states subgroup"""
        await NormalCall.got_links_from_nao.set()
        state = self.dispatcher.current_state()
        reply_to = self.get_message_to_reply_id()
        user = self.get_user_to_reply_id()
        await self.bot.send_message(text='redirecting reverse search, please wait',
                                    chat_id=user,
                                    reply_to_message_id=reply_to)
        resumed_file_handler = NewIncomingFile(self.bot, self.update, state)
        await resumed_file_handler.set_redirection_flag()
        await resumed_file_handler.manager.save_to_proxy()
        try:  # aiogram's error handlers dosent re-catch errors inside error handler
            links = await resumed_file_handler.yandex_redirected_search()
            if not any(links.values()):
                raise errors.SearchFailure
            capture = await resumed_file_handler.from_link_to_capture_process(links, [])
            await self.bot.edit_message_text(message_id=reply_to,
                                             chat_id=user,
                                             text=capture, reply_markup=menu_keyboards.confirm_keyboard)
        except errors.CustomError as e:
            self.exception = e
            await self.standart_error_reply()
        except selenium.common.exceptions.WebDriverException:
            self.exception = errors.SearchFailure
            await self.standart_error_reply()
