import asyncio

from aiogram import Bot
from aiogram.types.callback_query import CallbackQuery
from aiogram.utils.exceptions import RetryAfter

from parsers.yandex_parser import YandexParser


class PandoraBot(Bot):
    """class to update basic aiogram bot's methods"""
    def __init__(self, token: str, *args, **kwargs):
        super(PandoraBot, self).__init__(token=token, *args, **kwargs)


class Pandora(PandoraBot):
    """
    advanced custom bot class which also stored selenium based parser object
    """
    def __init__(self, token: str, yandex_parser: YandexParser, *args, **kwargs):
        self.yandex_parser = yandex_parser
        super(Pandora, self).__init__(token, *args, **kwargs)

    # bot mostly works with one message, which is reply to user's message

    async def edit_reply_markup_in_reply(self, callback: CallbackQuery, *args, **kwargs) -> None:
        """
        A decorator of aiogram.bot.edit_message_reply_markup method with presetted chat_id and message_id args.
        \nWorks based on the condition what message Callback came from its the target message
        of edit edit_message_reply_markup method.

        :param callback: CallbackQuery from message which markup will be edited
        :type callback: obj:CallbackQuery

        :param args: args of aiogram.bot.edit_message_reply_markup method
        :param kwargs: kwargs aiogram.bot.edit_message_reply_markup method

        :return: On succes changes reply markup of target message

        """
        await self.edit_message_reply_markup(chat_id=callback.message.chat.id,
                                             message_id=callback.message.message_id,
                                             *args, **kwargs)

    async def edit_bot_reply_text(self, callback: CallbackQuery, *args, **kwargs) -> None:
        """
        A decorator of aiogram.bot.edit_message_text method with chat_id and message_id presetted args.
        \nWorks based on the condition what message with inline keyboard its the target message of edit text method.

        :param callback: CallbackQuery from message which text will be edited
        :type callback: obj:CallbackQuery

        :param args: args of aiogram.bot.edit_message_text method
        :param kwargs: kwargs aiogram.bot.edit_message_text method

        :return: On succes changes text of target message

         """
        await self.edit_message_text(chat_id=callback.message.chat.id,
                                     message_id=callback.message.message_id, *args,
                                     **kwargs)

    async def resend_user_file(self, callback: CallbackQuery, *args, **kwargs) -> None:
        """
        A decorator of aiogram.bot.copy_message method with chat_id,
        from_chat_id, message_id, and caption presetted args.
        \nWorks based on the condition what message with inline keyboard its a reply
        to message with file, which user send to bot, and conversation happens in same chat.

        :param callback:  CallbackQuery from inline keyboard of message which is reply to file, send by user
        :type callback: obj:CallbackQuery

        :param args: args of aiogram.bot.copy_message method
        :param kwargs: kwargs of aiogram.bot.copy_message method

        :return: On succes, file sended by user send back in same chat with text of message,
         which CallbackQuery came from

        """
        await self.copy_message(chat_id=callback.message.chat.id, from_chat_id=callback.message.chat.id,
                                message_id=callback.message.reply_to_message.message_id,
                                caption=callback.message.text, *args, **kwargs)

    async def update_markup_in_another_chat(self, inline_callback: CallbackQuery, *args, **kwargs) -> None:
        """
        Wrapper of aiogram.bot.edit_message_reply_markup for
        updating reply markups in non-bot-conversation chats with presetted inline_message_id arg
        \nWorks based on the condition what message Callback came from its the target message
        of edit edit_message_reply_markup method.

        :param inline_callback:  callback from target of edit_message_markup method message
        :type inline_callback: CallbackQuery

        :param args: args of aiogram.bot.edit_message_reply_markup method
        :param kwargs: kwargs aiogram.bot.edit_message_reply_markup method

         :return: On succes changes reply markup of target message
        """
        try:
            await asyncio.sleep(delay=1.0)  # increase delay time
            await self.edit_message_reply_markup(inline_message_id=inline_callback.inline_message_id, *args,
                                                 **kwargs)
        except RetryAfter as e:
            await asyncio.sleep(delay=e.timeout)  # wait for the specified amount of time before trying again
            await self.edit_message_reply_markup(inline_message_id=inline_callback.inline_message_id, *args,
                                                 **kwargs)
