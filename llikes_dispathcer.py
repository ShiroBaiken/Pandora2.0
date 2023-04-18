from __future__ import annotations

from copy import copy
from typing import Any

import aiogram.types
import motor.motor_asyncio as async_motor
from aiogram.types import InlineKeyboardMarkup
from aiogram.types.callback_query import CallbackQuery
from bson import ObjectId

from Bot.keyboards.likes_keyboards import LikeKeyboard

client = async_motor.AsyncIOMotorClient("YOUR MONGO STORAGE ADDRESS HERE")
db = client["YOUR DATABASE NAME HERE"]
stored_posts = db["YOUR COLLECTION NAME HERE"]


class LikesKeyboardsHandler:
    """Class for handling reactions keyboards, attached to ready post in another chat, made by bot"""
    def __init__(self, callback: CallbackQuery, callback_data: dict):
        self.callback = callback
        self.callback_data = callback_data
        

    @staticmethod
    def increase_count_val(count: str) -> str:
        """increases str number by one"""
        return f'{int(count) + 1}'

    @staticmethod
    def decrease_count_val(count: str) -> str:
        """decreases str number by one"""
        return f'{int(count) - 1}'

    def update_count_val(self, user: str, users: list[str], count: str) -> str:
        """decrease or increase str number by one, depending on precense of given item into given list"""
        if user in users:
            return self.decrease_count_val(count)
        else:
            return self.increase_count_val(count)

    @staticmethod
    def get_button_index(button_text: str) -> int:
        """Due to the fact that the reaction places in the built-in keyboards that the bot attaches
        to the finished message are strict,
        they can be sorted by indexes in the updated list. This function returns the index
        placing reactions on these keyboards.
        """
        template = {
            'like': 0,
            'fine': 1,
            'disgust': 2,
            'dislike': 1
        }
        for key in template:
            if key in button_text:
                return template[key]

    @staticmethod
    def update_displayed_count(button: dict, updated_count: str) -> aiogram.types.InlineKeyboardButton:
        """changes value of text in corresponding 'Button' object after first found whitespace in str to given
        updated count"""
        button['text'] = f"{button['text'].split(' ')[0]} {updated_count}"
        return button

    def update_callback_count(self, button: dict, new_count: str) -> str:
        """re-assemble inline button's callback data without using aiogram methods"""
        parts = button['callback_data'].split(':')
        parts[2] = str(new_count)
        return self.compress_data(parts)

    def update_callback_data_in_button(self, button: dict, updated_count: str):
	"""Updates value in given InlineKeybouardButton object's callback data with given 
	updated count value"""
        button['callback_data'] = self.update_callback_count(button, updated_count)

    @staticmethod
    def compress_data(button_data: list[str]) -> str:
        """Joins separated parts of callback data to one string"""
        return ':'.join(button_data)

    def parse(self) -> tuple[Any, Any]:
        """Splits callback data to separate parts"""
        db_id = self.callback['data'].rsplit(':', maxsplit=1)[1]
        reaction = self.callback['data'].split(':', maxsplit=2)[1]
        return db_id, reaction

    @staticmethod
    async def call_to_db(db_id: str) -> dict:
        """Gets document of corresponding post by id"""
        async with await client.start_session() as s:  
            # By Motor's docs it shoud be 'async with' OR 'await'
            # But without this request to bd returns None.
            # Only God and creator
            # of this demonic spawn of misery and suffering knows, why
            db_vars = await stored_posts.find_one({"_id": ObjectId(db_id)})
            return db_vars

    async def update_counts(self, db_vars: dict, action: str, db_id: str) -> dict:
        """Updates counts and userlists in document, returns it as dict"""
        key = [x for x in db_vars if x.endswith(f'_{action}')][0]
        user = self.callback['from']['id']
        new_list = copy(db_vars[key])
        if user in new_list:
            new_list = [x for x in new_list if x != user]
        elif user not in db_vars[key]:
            new_list.append(user)
        async with await client.start_session() as s:
            await stored_posts.update_one({"_id": ObjectId(db_id)}, {'$set': {key: new_list}})
        db_vars.update({key: new_list})
        return db_vars

    @staticmethod
    def get_counts(db_vars: dict) -> list:
        """Retrives counts of reactions from document"""
        users_with_reactions = [x for x in db_vars if x.startswith('users_who')]
        counts = list(map(lambda x: len([y for y in db_vars[x] if y != '']), users_with_reactions))
        return counts

    @staticmethod
    def chose_reply_markup(counts: list, bd_id: str) -> InlineKeyboardMarkup:
        """Returns updated with new counts preset keybouard with reactions 
        based on value in callback data"""
        likes_generator = LikeKeyboard()
        if len(counts) == 2:
            return likes_generator.create_new_markup_with_two_reactions(bd_id)
        else:
            return likes_generator.create_new_markup_with_three_reactions(bd_id)

    async def update_values(self) -> InlineKeyboardMarkup:
        """Returns updated keyboard"""
        db_id, reaction = self.parse()
        stored_info = await self.call_to_db(db_id)
        updated = await self.update_counts(stored_info, reaction, db_id)
        count = self.get_counts(updated)
        new_markup = self.chose_reply_markup(count, db_id)
        for i in range(len(count)):
            if count[i] > 0:
                button = new_markup['inline_keyboard'][0][i]
                self.update_displayed_count(button, count[i])
                self.update_callback_data_in_button(button, count[i])
        return new_markup
