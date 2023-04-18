from dataclasses import dataclass, field
from typing import Callable, Optional

from aiogram.dispatcher import FSMContext
from aiogram.types.callback_query import CallbackQuery

from Bot.P_states import NormalCall


class ContentFilterHandler:
    """Look core.content_filter for more details"""
    buttons_from_markers = {
        'partial': 'Partial ignore',
        'absolute': 'Full ignore',
        'anal_ignore': 'Anal ignore'
    }

    indexes = {
        'partial': 0,
        'absolute': 1,
        'anal_ignore': 2
    }

    def restore_filter(self, unused_filters: list, filter_data: str) -> list[str]:
        """
        Returns used filter's name back to starage

        :param unused_filters: list from aiogram storage with filters names
        :param filter_data: key in self.indexes or self.buttons_from markers
            same as str swich in core.tag generators
        :return:
        """
        restored = unused_filters.insert(self.indexes[filter_data], self.buttons_from_markers[filter_data])
        return restored

    @staticmethod
    async def load_into(state: FSMContext) -> None:
        """adds lists of filters in storage so it can be used and changed"""
        await state.update_data({'not_applyed_filters': ['Partial ignore', 'Full ignore', 'Anal ignore']})

    @staticmethod
    async def load_from(state: FSMContext) -> list:
        """get list of unused filters from storage"""
        filters = await state.get_data('not_applyed_filters')
        return filters['not_applyed_filters']

    async def mark_filter_as_used(self, state: FSMContext, callback: CallbackQuery) -> None:
        """excludes filter name from list of filters in storage"""
        async with state.proxy() as data_storage:
            key = self.buttons_from_markers[callback.data.lstrip('menu:')]
            current_filters = data_storage['not_applyed_filters']
            await state.update_data({'not_applyed_filters': [x for x in current_filters if x != key]})


def useredit_counts(history: list):
    """creates index to add to state tame, to help managing consecutive useredits"""
    count = [x for x in history if x.startswith('NormalCall.UserInputEdit:tags_edited')]
    if not count:
        return '0'
    else:
        return str(len(count))


def edit_counter(func: Callable):
    """
    Decorator to enumerate user edits
    It adds str(len of useredit states names in history in storage)
    to end of useredit state name as example in 'get_state' in HistoryManager class below
    :param func: function which must return str (state name as str)
    :return: At succes, returns enumerated str. Number added to the end of str
    """

    async def count_edits(state: FSMContext):
        func_res = await func(state)
        async with state.proxy() as data_storage:
            if func_res.startswith('NormalCall.UserInputEdit:tags_edited'):
                func_res += useredit_counts(data_storage['history'])
        return func_res

    return count_edits


class HistoryManager:
    """ Realises history of changes, made by user.
     Counter used to switch between sets of buttons
     where one is "some changes already done" and another is
     "no changes done yet" """

    def __init__(self, proxy_data: dict, buffer: dict, last_state: Optional = None):
        self.proxy_data: dict = proxy_data
        self.buffer: dict = buffer
        self.last_state: str = last_state
        self.previous_capture: str = None
        self.counter = 0

    @staticmethod
    @edit_counter
    async def get_state(state: FSMContext) -> str:
        """Note this func works under decorator edit_counter which means
        it returns state name + int: get_state() -> 'NormalCall.UserInputEdit:tags_edited0'"""
        current_state = await state.get_state()
        return current_state

    async def start_history(self, state: FSMContext) -> None:
        """ initiates history in aiogram proxy (storage)"""
        # to avoid key erors, etc
        current_state = await self.get_state(state)
        self.buffer.update(history=[current_state])
        self.counter += 1

    async def history_update(self, state: FSMContext) -> None:
        """ adds current state in history"""
        state_to_add = await self.get_state(state)
        history = self.proxy_data['history']
        history_len = len(history)
        history.append(state_to_add)
        self.buffer.update(history=history)
        self.counter = history_len + 1

    async def history_reduce(self) -> None:
        """ sets last state in history as current
        shortens history by the last state"""
        history = self.proxy_data['history']
        history_len = len(history)
        self.buffer.update(history=history[0:-1])
        self.counter = history_len - 1

    def set_second_last_state(self) -> None:
        """skips one state in history to avoid stacking states in history
         used mostly to return to "initial" state"""
        self.last_state = self.proxy_data['history'][-2]

    def get_last_state(self) -> str:
        """returns last element from 'history' in storage"""
        return self.proxy_data['history'][-1]

    def get_previous_capture(self) -> dict:
        """returns last exist 'capture' dict from storage"""
        if self.last_state is None:
            self.set_second_last_state()
        return self.proxy_data[self.last_state]['tags']

    def set_current_to_previous_tags(self) -> None:
        """updates 'current_capture' key in storage by second last exist capture"""
        self.set_second_last_state()
        self.previous_capture = self.get_previous_capture()
        self.buffer.update({'current_capture': self.previous_capture})

    def did_redirect_exist(self) -> bool:
        return self.last_state == 'NormalCall.ForsedRedirect:sub_hashtags_generated'


class FSMManager:
    """mediator between aiogram's proxy, states, history of changes and data from parsing and user"""

    def __init__(self, state: FSMContext, data_storage: Optional = None):
        self.state: FSMContext = state
        self.data_storage: dict = data_storage
        self.buffer: dict = {}
        self.history_manager = HistoryManager(self.data_storage, self.buffer)

    async def get_current_data(self) -> None:
        """assignes data from storage as arg"""
        self.data_storage = await self.state.get_data()

    async def with_proxy(self, func: Callable, *args, **kwargs) -> any:
        """wrapper for functions to write down function result in storage"""
        async with self.state.proxy() as data:
            funcres = await func(*args, **kwargs)
            data.update(funcres)

    def update_history_manager(self) -> None:
        """initiates HistoryManager with fresh data from storage"""
        self.history_manager = HistoryManager(self.data_storage, self.buffer)

    def save_to_buffer(self, data: dict) -> None:
        # for usability all changes in gata first adds to build-in buffer dict
        # if full process of changes apply happens without errors
        # changes will be saved to db with below method save_to_proxy
        self.buffer.update(data)

    async def save_to_proxy(self) -> None:
        async with self.state.proxy() as data_storage:
            data_storage.update(self.buffer)

    async def generate_state_key(self, data: dict) -> dict:
        """changes in capture saved to buffer and db under name of state in which them generated
        \n Example: NormalCall.hastags_generated: {...}"""
        state_name = await self.state.get_state()
        return {state_name: data}

    async def save_to_buffer_under_state_key(self, data: dict) -> None:
        nested_save = await self.generate_state_key(data)
        self.buffer.update(nested_save)

    async def save_tags_under_state_name_key(self, tags: any) -> None:
        # a lot of changes in data storage associated with this spicific key below
        nested_save = await self.generate_state_key({'tags': tags})
        self.buffer.update(nested_save)

    def update_last_capture(self, new_capture: dict) -> None:
        """changes value of 'current capture' key in buffer"""
        self.buffer.update({'current_capture': new_capture})

    async def set_previous_state(self) -> None:
        """set bot in to last state saved in history manager"""
        await self.state.set_state(self.history_manager.last_state)

    async def menu_state_switch(self) -> None:
        """ switches between "some changes done"
         and "no changes done yet" states groups """
        #  since there direct relation between state, data, handlers and callbacks,
        #  this belongs here
        steps_counter = self.history_manager.counter
        if steps_counter >= 2:
            await NormalCall.EditMenu.ContinueEditing.in_menu.set()
        else:
            await NormalCall.EditMenu.in_menu.set()

    async def filter_menu_state_switch(self) -> None:
        """Same as "menu state swich", but for filters menu.
        \nFilters menu is substate of editing menu and its view
         depends only on amount of filters used, no matter how many other changes done,
         so on enter or exit this state, exit point calculates by steps counter"""
        steps_counter = self.history_manager.counter
        if steps_counter >= 2:
            await NormalCall.EditMenu.ContinueEditing.in_filters_menu.set()
        else:
            await NormalCall.EditMenu.in_filters_menu.set()

    async def set_default(self):
        """creates missing 'last_capture' and 'hictory' keys in storage with default values"""
        self.update_last_capture({
                "fandom": None,
                "character": None,
                "artist": None,
                "tags": None
            })
        if 'history' not in self.data_storage:
            await self.history_manager.start_history(self.state)
        await self.save_to_proxy()

    async def save_and_set_new_tags_to_buffer(self, new_tags: any) -> None:
        """updates capture under state key AND under 'current_capture' key in buffer"""
        await self.save_tags_under_state_name_key(new_tags)
        self.update_last_capture(new_tags)

    async def flush(self) -> None:
        """cleans storage and buffer"""
        # part of data in aiogram proxy must be keeped between rounds of file handling
        # or shoudnt if flags sets off
        self.buffer.clear()
        eraser = {}
        if self.data_storage:
            if 'sfw_flag' in self.data_storage:
                eraser.update({'sfw_flag': True})
            if 'ac_flag' in self.data_storage:
                eraser.update({'ac_flag': True})
            self.data_storage.clear()
        await self.state.set_data(eraser)

    async def set_sfw_flag(self):
        """adds key in storage which carried on between rounds of file handling or delete it if its already
        exist"""
        if 'sfw_flag' not in self.data_storage:
            self.save_to_buffer({'sfw_flag': True})
            await self.save_to_proxy()
        else:
            data_without_flag = {key: val for key, val in self.data_storage.items() if key != 'sfw_flag'}
            await self.state.set_data(data_without_flag)

    async def set_carnaval_flag(self):
        """adds key in storage which carried on between rounds of file handling or delete it if its already
        exist """
        if 'ac_flag' not in self.data_storage:
            self.save_to_buffer({'ac_flag': True})
            await self.save_to_proxy()
        else:
            data_without_flag = {key: val for key, val in self.data_storage.items() if key != 'ac_flag'}
            await self.state.set_data(data_without_flag)


@dataclass
class UserInputDataHandler:
    """Since telegram api does not provides some type of 'input window' for bots
    (at least simple one) user inputs must be sended by user as new message.
    This class provides dependenses between this new massage and previous data or user's actions"""
    manager: FSMManager = field(default=None)
    message_id: str = 0
    _proxy_data: dict = None
    state: FSMContext = None
    counter: int = field(default=0)

    @property
    def proxy_data(self):
        return self._proxy_data

    @proxy_data.setter
    def proxy_data(self, value):
        """Adds integer to state name to make possible for user do several edits
        and roll back(!) without data loss"""
        self._proxy_data = value
        if value is not None:
            if any([x for x in self._proxy_data.keys() if x.startswith('NormalCall.UserInputEdit')]):
                self.counter += len(
                    [x for x in self._proxy_data['history'] if x.startswith('NormalCall.UserInputEdit')])
            else:
                self.counter = 0


    async def save_to_buffer(self, data: dict) -> None:
        """saves data to FSMManager's buffer"""
        state_name = await self.state.get_state()
        state_key = f'{state_name}{self.counter}'
        self.manager.buffer.update({state_key: data})

    @staticmethod
    def prepare_save_edit(edited_capture) -> dict:
        return {'tags': edited_capture}

    async def save_edit(self, edited_capture) -> None:
        """adds userinput text, copy of previos capture and message id to data in buffer"""
        pre_edited = self.proxy_data['current_capture']
        input_to_proxy = {'input': pre_edited}
        input_to_proxy.update(self.prepare_save_edit(edited_capture))
        input_to_proxy.update({'message_id': self.message_id})
        await self.save_to_buffer(input_to_proxy)
        self.counter += 1
