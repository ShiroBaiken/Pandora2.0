from aiogram import Dispatcher, types
from aiogram.contrib.fsm_storage.mongo import MongoStorage
from aiogram.dispatcher import FSMContext
from aiogram.types import Message
from aiogram.types.callback_query import CallbackQuery
from aiogram.utils import executor
from pymongo.mongo_client import MongoClient

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    os.pardir)
)
sys.path.append(PROJECT_ROOT)

import Bot.FSM_manager as fsm
import Bot.button_commands as cmnds
import Bot.keyboards.likes_keyboards as likes
import Bot.keyboards.menu_keyboards as keyboards
from Bot.P_states import NormalCall, states_to_press_no
from Bot.bot_functions import Pandora
from Bot.error_handlers import CustomErrorHandler
from Bot.new_file_from_user import NewIncomingFile
from Bot.repost_handler import RepostToChannel
from core.exceptions import ApplyThreeReactionsKeyboard, NoContentAtNAOPage, NoSimilarPics, CustomError, SearchFailure, SpecialContent
from llikes_dispathcer import LikesKeyboardsHandler
from parsers.yandex_parser import YandexParser

client = MongoClient(os.environ['HOST'], 'YOUR IP ADRESS HERE')
db = client['YOUR DATABASE NAME HERE']
users = db['YOUR COLLECTION NAME HERE']
selenium = YandexParser(version=111)

storage = MongoStorage(host=os.environ['HOST'], port='YOUR IP ADRESS HERE', db_name='aiogram_fsm')
bot = Pandora(token=os.environ['BOT_TOKEN'], parse_mode='html', yandex_parser=selenium)
dp = Dispatcher(bot, storage=storage)

userinput_edit_handler = fsm.UserInputDataHandler()
Dispatcher.set_current(dp)


@dp.message_handler(commands='start', state='*')
async def greet_new_user(message: Message, state: FSMContext):  # state instace isnt used but still comes to handler
    """This handler is triggered when user starts chat with bot or sends '/start' command.
    Sends welcome message to user, sets bot into 'waiting_for_pic' (below - initial state)"""
    await NormalCall.waiting_for_pic.set()
    await message.answer("Hello, Im Pandora! Nice to meet you!")
    await message.answer('You can send me photo, gif or mpeg4 video \nand i will find description hashtags for '
                         'it... \nor not')


@dp.message_handler(commands='set_start', state='*')
async def set_reply(message: Message, state: FSMContext):  # message instace isnt used but still comes to handler
    """Service method, which can be used for reset conversation with bot"""
    await state.set_data({})
    await NormalCall.waiting_for_pic.set()


@dp.message_handler(commands='cancel', state='*')
async def cancel(message: Message, state: FSMContext):
    """Command to reset conversation.
    Resets data in storage, with saving special flags, if them exist.
    Sends user notification.
    Sets bot into initial state"""
    manager = fsm.FSMManager(state)
    if manager.data_storage:
        await manager.flush()
    await message.answer('waiting for file')
    await NormalCall.waiting_for_pic.set()


@dp.message_handler(commands='sfw', state='*')
async def sfw_flag(message: Message, state: FSMContext):  # message instace isnt used but still comes to handler
    """
    Adds or deletes corresponding flag key in storage, depending on its existance.
    """
    manager = fsm.FSMManager(state)
    await manager.get_current_data()
    await manager.set_sfw_flag()


@dp.message_handler(commands='carnaval', state='*')
async def carnaval_flag(message: Message, state: FSMContext):
    """
    Adds or deletes corresponding flag key in storage, depending on its existance.
    """
    manager = fsm.FSMManager(state)
    await manager.get_current_data()
    await manager.set_carnaval_flag()


@dp.message_handler(content_types=types.ContentTypes.PHOTO, state=NormalCall.waiting_for_pic)
async def reverse_search_for_hashtags(message: Message, state: FSMContext):
    """
     Handles incoming messages that contain photos by performing a reverse search
    for similar images using Sauce NAO. \n
    The results are processed into a string containing a list of possible image descriptions,
    which is then sent back to the user with a keyboard for confirmation.

    :param message: The incoming message that triggered the handler.
    :param state: The current state of the conversation.
    :return: None.  The function sends a reply message to the user.
    """
    # Prepare and save the incoming photo as a temporary file
    new_file_handler = NewIncomingFile(bot, message, state)
    await new_file_handler.prepare_file()
    await new_file_handler.already_posted_check()
    await new_file_handler.save_prepared_file()

    # Perform a reverse search for similar images using Sauce NAO
    links, artists = await new_file_handler.reverse_search()
    capture = await new_file_handler.from_link_to_capture_process(links, artists)
    # Send the results back to the user with a keyboard for confirmation
    await message.reply(capture, reply_markup=keyboards.confirm_keyboard)


@dp.message_handler(content_types=types.ContentTypes.VIDEO, state=NormalCall.waiting_for_pic)
@dp.message_handler(content_types=types.ContentTypes.ANIMATION, state=NormalCall.waiting_for_pic)
async def ask_for_likes(message: Message, state: FSMContext):
    """
    This handler triggers then user sends video or gif file to bot.
    Gathers data about incoming file, but doesn't performs any kind of reverse searh.
    Instead, sends user message with inline keyboard, asking if user like to attach keyboard with 3 reactions,
    or perform reverse search.

    - sets bot in 'NormalCall.LikesConfirmation.wait_for_likes_confirm' state
    """
    new_file_handler = NewIncomingFile(bot, message, state)
    await new_file_handler.prepare_file()
    await new_file_handler.already_posted_check()
    await new_file_handler.save_prepared_file()
    await new_file_handler.manager.save_to_proxy()
    await NormalCall.LikesConfirmation.wait_for_likes_confirm.set()
    await message.reply(text='Just likes?', reply_markup=keyboards.confirm_just_likes)


@dp.message_handler(state=NormalCall.UserInputEdit.waiting_for_input)
async def process_user_edit(message: Message, state: FSMContext):
    """
    This handler is triggered, when user sends messages with hashtags to bot in state 'waiting for input'.

    - performs edit with core.string_editor
    - Saves input from user and result of editing in aiogram's storage.
    - Sets bot in NormalCall.UserInputEdit.tags_edited state
    - Updates 'current_capture' and 'history' in storage.
    - Sends user reply with edit result and keyboard for confirmation

    """
    command = cmnds.UserInputEditCommand(bot)
    await command.process_and_save_userinput(userinput_edit_handler, message, state)


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='ok'),
                           state=[NormalCall.hashtags_generated,
                                  NormalCall.EditMenu.ContinueEditing.re_approve,
                                  NormalCall.ForsedRedirect.sub_hashtags_generated,
                                  NormalCall.UserInputEdit.tags_edited])
async def prepare_standart_repost(callback: CallbackQuery, state: FSMContext):
    """This handler is triggered when the user clicks the "Ok" button in the
    confirmation keyboard after bot replyes to user's message with file by message with capture"""
    command = cmnds.Agreed(bot)
    await command.prepare_file_repost(callback, state)


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='ok'),
                           state=[NormalCall.Error.error_rised, NormalCall.ForsedRedirect.sub_pre_redirected])
async def agree_with_error(callback: CallbackQuery, state: FSMContext):
    """
    This handler is triggered when the user clicks the "Ok" button in the
    confirmation keyboard after an error has occurred.
    It sets the bot's state to the initial state and clears the FSMManager's buffer and current state data.

    :param callback: callback from attached inline keyboard
    :param state: current state of bot
    :return: None. Bot sends notification about user can send new files
    """
    manager = fsm.FSMManager(state)
    await bot.edit_reply_markup_in_reply(callback, reply_markup=None)
    await bot.send_message(callback.from_user.id, 'waiting for file')
    await manager.flush()
    await NormalCall.waiting_for_pic.set()


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='ok'), state=NormalCall.got_links_from_nao)
async def exit_from_not_parsable_links(callback: CallbackQuery, state: FSMContext):
    """Special scenario occurs when links found from Sauce NAO leads to sites, which coudnt be parsed properly
    This hanler triggers when user press 'Ok' button on keyboard for confirmation attached to message with links"""
    await agree_with_error(callback, state)


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='ok'), state=NormalCall.Error.carnaval_error_rised)
async def carnaval_post(callback: CallbackQuery, state: FSMContext):
    """This handler triggers when SpecialContent error was rised
     and user pressed 'Ok' under mssage with SpecialContent error.
     Raises ApplyThreeReactionsKeyboard"""
    await bot.edit_reply_markup_in_reply(callback, reply_markup=None)
    raise ApplyThreeReactionsKeyboard


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='no'),
                           state=[NormalCall.hashtags_generated, NormalCall.Error.error_rised,
                                  NormalCall.got_links_from_nao])
async def first_time_show_change_menu(callback: CallbackQuery, state: FSMContext):
    """Triggered when user clicks 'NotOk' button in keyboard for confirmation without 'Back' button.
    (Means what no changes from user has been made yet)
    Sets bot into NormalCall.EditMenu.in_menu.
    Adds 'history' and 'current capture' keys in storage with default values.
    Displays 'menu' set of inline buttons to user"""
    command = cmnds.ButtonCommandNo(bot)
    await command.show_menu(callback, state)


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='no'),
                           state=NormalCall.LikesConfirmation.wait_for_likes_confirm)
async def resume(callback: CallbackQuery, state: FSMContext):
    """Triggers when user clicks 'Sauce' button after sending gif or video file to bot.
    Initiates reverse search and capture generation"""
    await NormalCall.waiting_for_pic.set()
    new_file_handler = NewIncomingFile(bot, callback, state)
    await new_file_handler.resume_reverse_search_for_prepared_file()


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='no'),
                           state=states_to_press_no)
async def show_change_menu_again(callback: CallbackQuery, state: FSMContext):
    """Triggers when user clicks 'NotOk' after some changes by user has been done.
    Sets bot into ContinueEditing subgroup.
    Shows user fluid set of 'menu' inline buttons, depending on previous user's actions"""
    command = cmnds.ButtonCommandNo(bot)
    await command.show_changes_menu_again(callback, state)


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='filters'), state=NormalCall.EditMenu.in_menu)
async def show_filters_menu_first_time(callback: CallbackQuery, state: FSMContext):
    """Triggers when user clicks 'Filters' button.
    Sets bot into NormalCall.EditMenu.in_filters_menu.
    Displays 'filter_menu' inline keyboard"""
    await NormalCall.EditMenu.in_filters_menu.set()
    command = cmnds.ShowFiltersMenuCommand(bot)
    await command.show_filters_menu(callback, state)


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='filters'),
                           state=NormalCall.EditMenu.ContinueEditing.in_menu)
async def show_filters_menu_again(callback: CallbackQuery, state: FSMContext):
    """Triggers when user already applyed one of the filters to capture and clicked 'Filters' button again.
    Shows user fluid set of 'filter_menu' inline buttons, depending on previous user's actions"""
    await NormalCall.EditMenu.ContinueEditing.in_filters_menu.set()
    command = cmnds.ShowFiltersMenuCommand(bot)
    await command.show_filters_menu(callback, state)


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='partial'),
                           state=[NormalCall.EditMenu.in_filters_menu,
                                  NormalCall.EditMenu.ContinueEditing.in_filters_menu])
async def partial_ignore(callback: CallbackQuery, state: FSMContext):
    """Trigger when user clicks button in menu of filters.
    For detail information about see core.content_filter.
    """
    await NormalCall.FilterApply.partial_filter_applyed.set()
    command = cmnds.ApplyFilterButtonCommand(bot)
    await command.filter_apply(callback, state, 'partial')


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='absolute'),
                           state=[NormalCall.EditMenu.in_filters_menu,
                                  NormalCall.EditMenu.ContinueEditing.in_filters_menu])
async def absolute_ignore(callback: CallbackQuery, state: FSMContext):
    await NormalCall.FilterApply.full_ignore_filters.set()
    command = cmnds.ApplyFilterButtonCommand(bot)
    await command.filter_apply(callback, state, 'full_ignore')


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='anal_ignore'),
                           state=[NormalCall.EditMenu.in_filters_menu,
                                  NormalCall.EditMenu.ContinueEditing.in_filters_menu])
async def anall_ignore(callback: CallbackQuery, state: FSMContext):
    await NormalCall.FilterApply.anal_filter_applyed.set()
    command = cmnds.ApplyFilterButtonCommand(bot)
    await command.filter_apply(callback, state, 'except_anal')


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='back'),
                           state=NormalCall.EditMenu.in_filters_menu)
async def back_from_filters(callback: CallbackQuery, state: FSMContext):
    """Returns user from filter menu to edit menu"""
    command = cmnds.BackButtonCommand(bot)
    await command.back_from_filters_menu(callback, state)


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='back'),
                           state=NormalCall.EditMenu.in_menu)
async def back_from_menu(callback: CallbackQuery, state: FSMContext):
    """Returns user from edit menu to keyboard for confirmation"""
    command = cmnds.BackButtonCommand(bot)
    await command.back_from_menu(callback, state)


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='back'),
                           state=NormalCall.EditMenu.ContinueEditing.in_menu)
async def back_from_menu_when_some_edits_done(callback: CallbackQuery, state: FSMContext):
    """Returns user from edit menu to keyboard for confirmation with 'back' button"""
    command = cmnds.BackButtonCommand(bot)
    await command.back_from_continue_edit_menu(callback, state)


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='back'),
                           state=NormalCall.EditMenu.ContinueEditing.re_approve)
async def back_from_confirmation(callback: CallbackQuery, state: FSMContext):
    """Shows user set of 'menu' buttons when user click 'back' button in keyboard for confirmation
    at the stage when bot asking for confirmation again after change, made by user"""
    command = cmnds.BackButtonCommand(bot)
    await command.back_from_re_approve(callback, state)


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='back'),
                           state=NormalCall.ForsedRedirect.sub_hashtags_generated)
async def undo_yandex_search(callback: CallbackQuery, state: FSMContext):
    """Reverts capture from results of reverse search with yandex to results of search with SauceNAO, if
    search with yandex was initiated by user"""
    command = cmnds.BackButtonCommand(bot)
    await command.undo_yandex_search(callback, state)


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='back'),
                           state=NormalCall.FilterApply.partial_filter_applyed)
async def undo_partial_filter(callback: CallbackQuery, state: FSMContext):
    """Triggers when user clicks back button after apllying filter to capture.
    Retrives previous capture from storage, restores name of partial filter in filterslist in storage"""
    command = cmnds.BackButtonCommand(bot)
    await command.undo_filter_apply(callback, state, 'partial')


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='back'),
                           state=NormalCall.FilterApply.full_ignore_filters)
async def undo_absolute_filter(callback: CallbackQuery, state: FSMContext):
    """Triggers when user clicks back button after apllying filter to capture.
        Retrives previous capture from storage, restores name of absolute filter in filterslist in storage"""
    command = cmnds.BackButtonCommand(bot)
    await command.undo_filter_apply(callback, state, 'absolute')


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='back'),
                           state=NormalCall.FilterApply.anal_filter_applyed)
async def undo_anal_filter(callback: CallbackQuery, state: FSMContext):
    """Triggers when user clicks back button after apllying filter to capture.
        Retrives previous capture from storage, restores name of anal filter in filterslist in storage"""
    command = cmnds.BackButtonCommand(bot)
    await command.undo_filter_apply(callback, state, 'anal_ignore')


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='back'),
                           state=NormalCall.UserInputEdit.tags_edited)
async def undo_userinput_edit(callback: CallbackQuery, state: FSMContext):
    """Triggers when user clicks back button after edit by user input.
        Retrives previous capture from storage, DELETES LAST 2 MESSAGES IN CHAT WITH USER"""
    command = cmnds.BackButtonCommand(bot)
    await command.undo_edit(callback, state)


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='edit'),
                           state=[NormalCall.EditMenu.in_menu,
                                  NormalCall.UserInputEdit.pre_edit,
                                  NormalCall.EditMenu.ContinueEditing.in_menu])
async def prepare_userinput_edit(callback: CallbackQuery, state: FSMContext):
    """Triggers when user clicks 'Edit' button in edit menu,
    sends user guide for userinput, hides inline keyboard attached."""
    command = cmnds.UserInputEditCommand(bot)
    await command.set_edit(userinput_edit_handler, callback, state)


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='yandex'), state=[NormalCall.EditMenu.in_menu,
                                                                                    NormalCall.EditMenu.ContinueEditing.in_menu])
async def forced_yandex_search(callback: CallbackQuery, state: FSMContext):
    """Triggers when user clicks 'Search again with yandex' in edit menu.
    Starts selenium, if no instance has been created yet"""
    command = cmnds.ForceRedirectCommand(bot)
    await command.wrap_yandex_search(callback, state)
    new_file_handler = NewIncomingFile(bot, callback, state, state_group=NormalCall.ForsedRedirect)
    await new_file_handler.set_redirection_flag()
    links = await new_file_handler.yandex_redirected_search()
    capture = await new_file_handler.from_link_to_capture_process(links, artists=[])
    await bot.edit_bot_reply_text(callback, text=capture, reply_markup=keyboards.confirm_board_with_back)


@dp.callback_query_handler(keyboards.menu_callbacks.filter(marker='buttons'),
                           state=[NormalCall.LikesConfirmation.wait_for_likes_confirm,
                                  NormalCall.EditMenu.in_menu,
                                  NormalCall.EditMenu.ContinueEditing.in_menu])
async def confirmed_likes(callback: CallbackQuery, state: FSMContext):
    """Triggers when user clicks 'Just likes' in edit menu.
    Sends recived file back to user with preset keyboard of 3 reactions to repost."""
    command = cmnds.LikesConfirmed(bot)
    await command.prepare_anal_carnaval_post(callback, state)
    await NormalCall.posting.set()


@dp.callback_query_handler(likes.likes_callbacks.filter(action=['like', 'dislike', 'fine', 'disgust']), state='*')
async def count_update(callback: CallbackQuery, callback_data: dict):
    """updates counts in keyboards with reactions.
    See likes_dispather for more info."""
    likes_handler = LikesKeyboardsHandler(callback, callback_data)
    new_markup = await likes_handler.update_values()
    await bot.update_markup_in_another_chat(callback, reply_markup=new_markup)


@dp.errors_handler(exception=ApplyThreeReactionsKeyboard)
async def special_content_found(update, exception):
    """Triggers when ApplyThreeReactionsKeyboard raised.
    Resends file back to user with preset keyboard of 3 reactions and button for repost"""
    err_handler = CustomErrorHandler(update=update, dp=dp, exc=exception, bot=bot)
    await err_handler.anal_carnaval_error_reply()
    return True


@dp.errors_handler(exception=NoContentAtNAOPage)
@dp.errors_handler(exception=NoSimilarPics)
async def error_redirect(update, exception):
    """Triggers when error occurs during parsing Sauce NAO page, initiates reverse search with Yandex"""
    err_handler = CustomErrorHandler(update=update, dp=dp, exc=exception, bot=bot)
    await err_handler.error_search_redirect()
    return True


@dp.errors_handler(exception=SpecialContent)
async def carnaval_error_reply(update, exception):
    """Trigger when special words occurs in parsed file descriptions, initiates reply to file send by user,
     with keyboard asks user need edit result or perform repost with preset reactions keyboard."""
    err_handler = CustomErrorHandler(update=update, dp=dp, exc=exception, bot=bot)
    await err_handler.standart_error_reply()
    await NormalCall.Error.carnaval_error_rised.set()
    return True


@dp.errors_handler(exception=CustomError)
@dp.errors_handler(exception=SearchFailure)
async def reply_for_custom_errors(update, exception):
    """Triggers when rest of CustromErrors occurs, sends user reply to file,
    with message, containing error class name end error message, with keyboard for confirmation applyed"""
    err_handler = CustomErrorHandler(update=update, dp=dp, exc=exception, bot=bot)
    await err_handler.standart_error_reply()
    await NormalCall.Error.error_rised.set()
    return True


@dp.inline_handler(lambda inline_query: inline_query.query.isalpha() or inline_query.query == '', state='*')
async def chat_ivitation(inline_query: types.InlineQuery):
    """Handles empty or text inline queries which is not contain numbers"""
    await bot.answer_inline_query(inline_query_id=inline_query.id, results=[],
                                  is_personal=True, cache_time=60, switch_pm_text='To bot', switch_pm_parameter='start')


@dp.inline_handler(lambda inline_query: inline_query.query.startswith('menu:repost'), state=NormalCall.posting)
async def repost_inline_handler(inline_query: types.InlineQuery, state: FSMContext):
    """Handles cross-chat post creating by bot"""
    repost_command = RepostToChannel(state, inline_query, bot)
    await repost_command.create_post()


async def shutdown(dispatcher: Dispatcher):
    """disconnects bot from storage"""
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()


if __name__ == "__main__":
    executor.start_polling(dp, on_startup=print('started!'), on_shutdown=shutdown)
