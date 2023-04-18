from aiogram import types
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.callback_data import CallbackData


class MenuCallback(CallbackData):
    id: str
    marker: str


preset_buttons = {
    'OK': ('OK', 'ok'),
    'No': ('Not OK', 'no'),
    'Back': ('Back', 'back'),
    'Yandex': ('Search again with Yandex', 'yandex'),
    'Filters': ('Tags filters', 'filters'),
    'Edit': ('Edit tags', 'edit'),
    'Sause': ('Sause', 'no'),
    'Likes': ('Just likes', 'buttons'),
    'Partial ignore': ('Partial ignore filters', 'partial'),
    'Full ignore': ('Almost all existing tags', 'absolute'),
    'Anal ignore': ('Ignore anal check', 'anal_ignore'),
    'Ignore sex': ('Ignore sex presistance', 'ignore sex'),

}

menu_callbacks = MenuCallback('menu', 'marker') # callback data generator


class InlineBoard:
    """Skeleton for adding new classes"""
    def __init__(self, row_width: int):
        self.row_width = row_width
        self.menu_cb = menu_callbacks


    def generate_button(self, buttondata: tuple):
        pass

    def add_buttons_per_row(self, buttons: any):
        pass

    def wrap_into_keyboard(self):
        pass


class PandoraInlineBoard(InlineBoard):
    """Basic generator for InlineKeyboard objects"""

    def __init__(self, row_width: int = 1):
        super().__init__(row_width)

    def generate_button(self, buttondata: tuple):
        """Creates InlineKeyboardButton with text and callback from tuple context"""
        return types.InlineKeyboardButton(text=buttondata[0], callback_data=self.menu_cb.new(marker=buttondata[1]))

    def add_buttons_per_row(self, buttons: Iterable):
            """
            Separates list of InlineKeyboardButtons object per rows.
            Returns InlineKeyboardMarkup object.
            """
        rows = len(buttons) // self.row_width
        keyboard = InlineKeyboardMarkup(row_width=self.row_width)
        for i in range(rows):
            current_row = tuple(buttons[x] for x in range(i * self.row_width, i * self.row_width + self.row_width))
            keyboard.row(*current_row)
        if len(buttons) % self.row_width != 0:
            last_row = tuple(buttons[x] for x in range(self.row_width * rows, len(buttons)))
            keyboard.row(*last_row)
        return keyboard

    def list_of_buttons_fromkeys(self, keys: Iterable):
        """Generates list of preset InlineKeyboardButton objects by given list of keys"""
        output = []
        for key in keys:
            output.append(self.generate_button(preset_buttons[key]))
        return output

    def build_fromkeys(self, keys: list):
        """
        Generates InlineKeyboardMarkup with preset buttons from list of given keys
        """
        buttons = self.list_of_buttons_fromkeys(keys)
        return self.add_buttons_per_row(buttons)


def filters(filters_keys):
    """
    Returns InlineKeyboardMarkup for 'filters_menu' keyboard
    """
    keyb_builder = PandoraInlineBoard()
    keys = filters_keys + ['Back']
    buttonlist = keyb_builder.list_of_buttons_fromkeys(keys)
    return keyb_builder.add_buttons_per_row(buttonlist)


def confirm_board():
    """
    Returns InlineKeyboardMarkup for keyboard for confirmaton
    """
    keyb_builder = PandoraInlineBoard(2)
    buttons_keys = ['OK', 'No']
    return keyb_builder.add_buttons_per_row(keyb_builder.list_of_buttons_fromkeys(buttons_keys))


def menu_keyboard_redirect_switch(proxy_data):
    """
    Returns InlineKeyboardMarkup for 'menu_keyboard',
    with 'YandexSearch' button excluded or not, depending on special value in connected aiogram storage 
    """
    if 'redirection_flag' in proxy_data.keys():
        if proxy_data['redirection_flag'] is True:
            return menu_without_redirect
        if proxy_data['redirection_flag'] is False:
            return menu_with_redirect
    else:
        return menu_with_redirect

# preset InlineKeyboardMarkup objects
confirm_just_likes = PandoraInlineBoard(2).build_fromkeys(['Likes', 'Sause'])
confirm_keyboard = confirm_board()
confirm_board_with_back = PandoraInlineBoard(2).build_fromkeys(['OK', 'No', 'Back'])
menu_with_redirect = PandoraInlineBoard().build_fromkeys(['Yandex', 'Filters', 'Edit', 'Likes', 'Back'])
menu_without_redirect = PandoraInlineBoard().build_fromkeys(['Filters', 'Edit', 'Likes', 'Back'])
