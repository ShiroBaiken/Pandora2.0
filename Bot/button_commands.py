from typing import Optional

import aiogram.types
from aiogram.dispatcher import FSMContext
from aiogram.types import CallbackQuery

from Bot.FSM_manager import FSMManager, ContentFilterHandler, UserInputDataHandler
from Bot.P_states import NormalCall
from Bot.bot_functions import Pandora
from Bot.keyboards import menu_keyboards as keyboards
from Bot.keyboards.likes_keyboards import LikeKeyboard
from core.string_collector import StringCollector
from core.string_editor import CaptureEditor
from core.tag_generator import TagGeneratorHandler

content_filters_manager = ContentFilterHandler()


class ButtonCommand:
    """
    Basic class to represent user action with inline keyboards, provided by bot
    """

    def __init__(self, bot, fsm_manager: Optional = None):
        """

        :param bot: Bot.bot_functions Pandora, interhited from aiogram's bot class
        :param fsm_manager: Bot.FSM_manager FSMManager
        """
        self.bot: Pandora = bot
        self.fsm_manager: FSMManager = fsm_manager

    async def init_manager(self, state) -> None:
        """
        Proxy data and states changes when user press button.
        This method makes build-in FSMManager work with updated data

        :param state: aiogram.dispatcher.filters.state State
        :return: on succes, FSMManager gets fresh data from storage.
            If specific key in data is missing, creates history and empty
            current_capture dict in data
        """
        current_data = await state.get_data()
        self.fsm_manager = FSMManager(state, current_data)
        if "current_capture" not in current_data:
            await self.fsm_manager.set_default()

    async def reply_with_last_capture_from_buffer(self, callback: CallbackQuery, *args, **kwargs) -> None:
        """
        Converts 'current_capture' data from FSMManager buffer to str and updates message text via
        Pandora edit_bot_reply_text method

        :param callback: CallbackQuery
        :param args: args of aiogram.bot.edit_message_text method
        :param kwargs: kwargs of aiogram.bot.edit_message_text method
        :return: on succes, updates text of target message
        """
        hashtags = self.fsm_manager.buffer['current_capture']
        capture = StringCollector(hashtags).to_string()
        await self.bot.edit_bot_reply_text(callback, *args, **kwargs, text=capture)

    async def edit_reply_markup_with_last_capture_from_buffer(self, callback: CallbackQuery,
                                                              markup: aiogram.types.InlineKeyboardMarkup,
                                                              *args, **kwargs) -> None:
        """
        Same as reply_with_last_capture_from_buffer, but with ability to change reply markup
        of target message with Pandora edit_reply_markup_in_reply method

        :param callback: CallbackQuery
        :param markup: aiogram.types.InlineKeyboardMarkup
        :param args: args of aiogram.bot.edit_message_reply_markup method
        :param kwargs: kwargs of aiogram.edit_message_reply_markup method
        :return: On succes, changes both text and reply markup of target message
        """
        hashtags = self.fsm_manager.buffer['current_capture']
        capture = StringCollector(hashtags).to_string()
        await self.bot.edit_reply_markup_in_reply(callback, *args, **kwargs,
                                                  reply_markup=markup, text=capture)

    async def finish(self, state: FSMContext) -> None:
        """
        Cleans storage and FSMManager buffer with seted flags saving, if nessesary
        \nSets bot in awaitment of file state
        :param state: aiogram.dispatcher.filters.state State
        :return: None
        """
        await self.fsm_manager.flush()
        await NormalCall.waiting_for_pic.set()


class BackButtonCommand(ButtonCommand):
    """ implements mechanism for 'back' button in bot"""

    def __init__(self, bot, capture: Optional = None):
        """
        :param bot: Bot.bot_functions Pandora, interhited from aiogram's bot class
        :param capture: dict of filtered and converted by core.tag_generator hashtags
        """
        self.capture = capture
        super(BackButtonCommand, self).__init__(bot)

        #  Note: changes in 'history' and storage fields generated only if captures, generated
        # by bot, where changed. Else only current state and buttons,
        # showed to user, changed by this and all methods below

    async def undo_filter_apply(self, callback: CallbackQuery, state: FSMContext, filter_name: str) -> None:
        """
        Rollback core.content_filter applyng depending on how much filters apllyed and order of them

        :param callback: CallbackQuery
        :param state: aiogram.dispatcher.filters.state State
        :param filter_name: key in ContentFilterHandler buttons_from_markers and indexes
        :return: On succes, restores last used filter in
            list of unused filters in storage and changes current capture to point before filter was applyed
        """
        await self.init_manager(state)
        self.capture = self.fsm_manager.history_manager.get_previous_capture()
        self.fsm_manager.history_manager.set_second_last_state()
        await self.fsm_manager.history_manager.history_reduce()
        await self.fsm_manager.filter_menu_state_switch()
        reply_markup_buttons_names = await content_filters_manager.load_from(state)
        content_filters_manager.restore_filter(reply_markup_buttons_names, filter_name)
        self.fsm_manager.history_manager.set_current_to_previous_tags()
        self.fsm_manager.save_to_buffer({'not_applyed_filters': reply_markup_buttons_names})
        reply_markup = keyboards.filters(reply_markup_buttons_names)
        await self.fsm_manager.save_to_proxy()
        capture = StringCollector(self.fsm_manager.history_manager.previous_capture).to_string()
        await self.bot.edit_bot_reply_text(callback, text=capture,
                                           reply_markup=reply_markup)

    async def back_from_filters_menu(self, callback: CallbackQuery, state: FSMContext) -> None:
        """show user set buttons of edit menu"""
        await NormalCall.EditMenu.previous()
        async with state.proxy() as data_storage:  # no special function or significant changes in storage needed
            markup = keyboards.menu_keyboard_redirect_switch(data_storage)
            await self.bot.edit_reply_markup_in_reply(callback, reply_markup=markup)

    async def back_from_menu(self, callback: CallbackQuery, state: FSMContext) -> None:
        """
        return user to confirmation menu (ok/not_ok) of inline buttons
        """
        await self.init_manager(state)
        if 'NormalCall.ForsedRedirect.sub_geting_tags' not in self.fsm_manager.data_storage.keys():
            self.fsm_manager.save_to_buffer({'redirection_flag': False})  # this prevents 'search with yandex' button
            # to be  hidden when menu buttons show up and helps avoid errors when using it
            await self.fsm_manager.save_to_proxy()
            await NormalCall.hashtags_generated.set()
        elif 'NormalCall.ForsedRedirect.sub_hashtags_generated' in self.fsm_manager.data_storage.keys():
            await NormalCall.ForsedRedirect.sub_hashtags_generated.set()
        await self.bot.edit_reply_markup_in_reply(callback, reply_markup=keyboards.confirm_keyboard)

    async def back_from_continue_edit_menu(self, callback: CallbackQuery, state: FSMContext) -> None:
        """return user to confirmation menu (ok/not_ok) with 'back' button"""
        await NormalCall.EditMenu.ContinueEditing.re_approve.set()
        await self.bot.edit_reply_markup_in_reply(callback, reply_markup=keyboards.confirm_board_with_back)

    async def back_from_re_approve(self, callback: CallbackQuery, state: FSMContext) -> None:
        """
        show up set of menu buttons from state, where some changes where applyed and bot asks user to confirm them
        """
        # user can do different changes with capture utill all bot's methods had expired
        # to enable this feature this function is more complicated, than could be
        await self.init_manager(state)
        self.fsm_manager.history_manager.set_second_last_state()
        self.fsm_manager.save_to_buffer({'redirection_flag': self.fsm_manager.data_storage['redirection_flag']})
        if self.fsm_manager.history_manager.did_redirect_exist():
            self.fsm_manager.save_to_buffer({'redirection_flag': False})
        await self.fsm_manager.set_previous_state()
        await self.fsm_manager.history_manager.history_reduce()
        await self.fsm_manager.menu_state_switch()
        self.fsm_manager.history_manager.set_current_to_previous_tags()
        markup = keyboards.menu_keyboard_redirect_switch(self.fsm_manager.buffer)
        await self.fsm_manager.save_to_proxy()
        capture = StringCollector(self.fsm_manager.history_manager.previous_capture).to_string()
        await self.bot.edit_bot_reply_text(callback, text=capture, reply_markup=markup)

    async def undo_yandex_search(self, callback: CallbackQuery, state: FSMContext) -> None:
        """
        Reverts result of reverse search via yandex if search was started from edit menu
        """
        await self.init_manager(state)
        self.fsm_manager.history_manager.set_second_last_state()
        self.fsm_manager.save_to_buffer({'redirection_flag': False})
        await self.fsm_manager.history_manager.history_reduce()
        await self.fsm_manager.menu_state_switch()
        self.fsm_manager.history_manager.set_current_to_previous_tags()
        await self.fsm_manager.save_to_proxy()
        capture = StringCollector(self.fsm_manager.history_manager.previous_capture).to_string()
        await self.bot.edit_bot_reply_text(callback, text=capture,
                                           reply_markup=keyboards.menu_with_redirect)

    async def undo_edit(self, callback: CallbackQuery, state: FSMContext) -> None:
        """
        undo user edit with deleting edit messages and new reply message, created by bot
        """
        await self.init_manager(state)
        self.fsm_manager.history_manager.set_second_last_state()
        message_to_change_id = self.fsm_manager.data_storage[
            self.fsm_manager.history_manager.get_last_state()]['message_id']
        await self.fsm_manager.history_manager.history_reduce()
        await self.fsm_manager.menu_state_switch()
        UserInputDataHandler.counter -= 1
        self.fsm_manager.history_manager.set_current_to_previous_tags()
        last_message_id = callback.message.message_id
        await self.bot.delete_message(state.chat, last_message_id)
        await self.bot.delete_message(state.chat, last_message_id - 1)
        markup = keyboards.menu_keyboard_redirect_switch(self.fsm_manager.buffer)
        await self.fsm_manager.save_to_proxy()
        capture = StringCollector(self.fsm_manager.history_manager.previous_capture).to_string()
        await self.bot.edit_message_text(chat_id=state.chat, message_id=message_to_change_id,
                                         text=capture,
                                         reply_markup=markup)


class ApplyFilterButtonCommand(ButtonCommand):

    async def filter_apply(self, callback: CallbackQuery, state: FSMContext, filter_value: str) -> None:
        """
        Applyes chosen core.content_filter to capture in storage,
        saves result in storage under name of chosen filter key.
        \nDeletes chosen filter name from list of unused filters in storage
        """
        await self.init_manager(state)
        generator = TagGeneratorHandler(self.fsm_manager.data_storage["NormalCall:reduce_tags"], filter_value)
        filter_generated_tags = generator.recognize_and_generate_hasttags()
        await self.fsm_manager.save_tags_under_state_name_key(filter_generated_tags)
        self.fsm_manager.update_last_capture(filter_generated_tags)
        await content_filters_manager.mark_filter_as_used(state, callback)
        await self.fsm_manager.history_manager.history_update(state)
        await self.fsm_manager.save_to_proxy()
        await self.reply_with_last_capture_from_buffer(callback, reply_markup=keyboards.confirm_board_with_back)


class ButtonCommandNo(ButtonCommand):

    async def show_changes_menu_again(self, callback: CallbackQuery, state: FSMContext) -> None:
        """
        changes inline keyboard in message to set of basic menu buttons
        \nsets bot in NormalCall.EditMenu.ContinueEditing state subgroup
        """
        await NormalCall.EditMenu.ContinueEditing.in_menu.set()
        await self.init_manager(state)
        markup = keyboards.menu_keyboard_redirect_switch(self.fsm_manager.data_storage)
        await self.bot.edit_reply_markup_in_reply(callback, reply_markup=markup)

    async def show_menu(self, callback: CallbackQuery, state: FSMContext) -> None:
        """
        changes inline keyboard in message to set of basic menu buttons
        \nloads nesessary data of filters class into aiogram storage
        \nin chain of re-editing inline markups and text in same bot message should be used first
        """
        await NormalCall.EditMenu.in_menu.set()
        await content_filters_manager.load_into(state)
        await self.init_manager(state)
        markup = keyboards.menu_keyboard_redirect_switch(self.fsm_manager.data_storage)
        await self.bot.edit_reply_markup_in_reply(callback, reply_markup=markup)


class ShowFiltersMenuCommand(ButtonCommand):

    async def show_filters_menu(self, callback: CallbackQuery, state: FSMContext) -> None:
        """changes inline keyboard in message to set of Filter buttons"""
        filt_menu_buttons = await content_filters_manager.load_from(state)
        filt_menu = keyboards.filters(filt_menu_buttons)
        await self.bot.edit_reply_markup_in_reply(callback, reply_markup=filt_menu)


class ForceRedirectCommand(ButtonCommand):

    async def wrap_yandex_search(self, callback: CallbackQuery, state: FSMContext) -> None:
        """aiogram decorations to aware user of call via selenium
        \nsets bot in initial state of ForsedRedirect state group"""
        await self.bot.edit_bot_reply_text(callback, text='redirecting, please wait')
        await self.bot.answer_callback_query(callback_query_id=callback.id, text='redirecting, please wait')
        await self.init_manager(state)
        await NormalCall.ForsedRedirect.sub_pre_redirected.set()


class UserInputEditCommand(ButtonCommand):

    def refresh_edit_saver(self, edit_save_handler: UserInputDataHandler, state: FSMContext) -> None:
        """assigment of UserInputDataHandler args with current temporal data"""
        edit_save_handler.manager = self.fsm_manager
        edit_save_handler.proxy_data = self.fsm_manager.data_storage
        edit_save_handler.state = state

    async def set_edit(self, edit_save_handler: UserInputDataHandler, callback: CallbackQuery,
                       state: FSMContext) -> None:
        """sends instruction for useredit, bot sets in waiting for next user's text message
        Note: this method breaks chain of re-editing same bot message, next methods which rely on special message id
        or messages order must be used with care"""
        await NormalCall.UserInputEdit.pre_edit.set()
        await self.init_manager(state)
        edit_save_handler.manager = self.fsm_manager
        edit_save_handler.message_id = callback.message.message_id
        updated_capture = f"{callback.message.text}\n \n Now send me message, " \
                          f"how you like to edit post: send me tags, which already in subscribtion," \
                          f"if you want to delete them, send me '#ecchi', '#nude' or '#sfw' if you want " \
                          f"to edit content rate," \
                          f"send me new tags if you want to add them: " \
                          f"capitalized words atter '#' counts as character or fandom name, " \
                          f"otherwise they count as usual tags and placed at the end of the description." \
                          f" Also, you must type 'By:' before artist hashtag \n \nEnter your hashtags below"
        await self.bot.edit_bot_reply_text(callback, text=updated_capture,
                                           reply_markup=None)
        await NormalCall.UserInputEdit.waiting_for_input.set()

    async def process_and_save_userinput(self, edit_save_handler: UserInputDataHandler,
                                         message: aiogram.types.Message, state: FSMContext) -> None:
        """Stores text from users's message, recived in 'waiting_for_userinput' state and capture,
        generated by bot in storage. \n
        Performs edit of capture depending on user's message context with CaptureEditor,
        saves result in storage and updates 'current_capture' key in storage with it.
        Sets bot to 'NormalCall.UserInputEdit.tags_edited' state."""
        await self.init_manager(state)
        self.refresh_edit_saver(edit_save_handler, state)
        user_input = message.text
        editor = CaptureEditor(self.fsm_manager.data_storage['current_capture'], user_input)
        new_capture = editor.edit_by_user_input()
        await NormalCall.UserInputEdit.next()
        await edit_save_handler.save_edit(new_capture)
        await self.fsm_manager.history_manager.history_update(state)
        self.fsm_manager.update_last_capture(new_capture)
        await self.fsm_manager.save_to_proxy()
        capture_text = editor.to_string()
        reply_to = self.fsm_manager.data_storage['NormalCall:waiting_for_pic']['message_id']
        await self.bot.send_message(chat_id=message.chat.id, text=capture_text,
                                    reply_to_message_id=reply_to,
                                    reply_markup=keyboards.confirm_board_with_back)


class LikesConfirmed(ButtonCommand):

    async def prepare_anal_carnaval_post(self, callback: CallbackQuery, state: FSMContext) -> None:
        """Creates preset keyboard with 3 reactions and adds 'Post' button with id, generated by
        uuid4 to it. Resends user file back to user with named keyboard."""
        """ Note: this method dont apply caption to user's image"""
        await self.init_manager(state)
        likes_keyboard_generator = LikeKeyboard()
        three_likes_buttons = likes_keyboard_generator.create_new_markup_with_three_reactions('0')
        reply_markup = likes_keyboard_generator.add_repost_button(three_likes_buttons, 2)
        await self.bot.resend_user_file(callback, reply_markup=reply_markup)


class Agreed(ButtonCommand):

    async def user_agreed_with_unsucceful_result(self, callback: CallbackQuery, state: FSMContext) -> None:
        """cleans storage and FSMManager's buffer, re-starts conversation round.

        Used in all custrom error cases, which interhit from CustromError and case where SauceNao dont provide links
        for parsable imageboards"""
        await self.finish(state)
        await self.bot.edit_reply_markup_in_reply(callback, reply_markup=None)

    async def prepare_file_repost(self, callback: CallbackQuery, state: FSMContext) -> None:
        """
        Creates sample of post with picture, sended to bot, capture and likes inline keyboard in chat
        with user. Ends conversation round instead, if no parsable links found on SauseNao

        :param callback: CallbackQuery
        :param state: FSMContext
        :return: on succes, bot sends copy of user picture with capture and decorative likes keyboard with 'Post'
            button
        """
        await self.init_manager(state)
        capture = self.fsm_manager.data_storage['current_capture']
        if type(capture) != dict:  # parsing NAO can return str instead of dict if only links to unparsable
            # imageboards were found, this counts as error
            await self.user_agreed_with_unsucceful_result(callback, state)
        else:
            await NormalCall.posting.set()
            await self.bot.edit_reply_markup_in_reply(callback, reply_markup=None)
            likes_handler = LikeKeyboard()
            two_likes_buttons = likes_handler.create_new_markup_with_two_reactions('0')  # content filter raises custom
            # error for 3 likes button keyboard, same happens if user chose special command
            # so in general way theres no case, when 3-buttons keyboard can be needed,
            # this inline keyboard is decorative
            reply_markup = likes_handler.add_repost_button(two_likes_buttons, 1)
            await self.bot.resend_user_file(callback, reply_markup=reply_markup)
