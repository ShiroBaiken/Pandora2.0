import typing

from bson import ObjectId
from pymongo import MongoClient
from os import environ as venv

from core import exceptions


client = MongoClient(venv['HOST'], 27017)
db = client["YOUR DATABASE NAME HERE"]
nest_collection = db["YOUR COLLECTION NAME HERE"]

tag_exeptions = ('your tags to exlude here')

not_ok = nest_collection.find_one({"_id": ObjectId(venv['RESTRICTED'])})

anal_carnaval = ('your list of special tags here')


class ContentFilter:
    """
    Class to recognise and mark as 'restricted' content of picture, user sended to bot,
    based on parsed tags from reverse search result
    """

    def __init__(self, parsed_common_tags: dict, filter_ignore: str, anal_tags: list = None, restricted: list = None,
                 exclusion: list = None):
        self.filter_ignore = filter_ignore
        self.parsed_common_tags = parsed_common_tags
        self.special_tags = anal_tags
        self.restricted = restricted
        self.exclusion = exclusion

    filters: typing.ClassVar[dict] = {
        'standart': 'standart_filter',
        'partial': 'ignore_all_except_anal',
        'full_ignore': 'ignore_all',
        'except_anal': 'ignore_anal',
        'ignore_sex': 'ignore_sex'
    }

    @staticmethod
    def get_by_value(queue: str) -> str:
        """for searching in 'not_ok' since multiple values can match one key"""
        for a, b in not_ok.items():
            if queue in a:
                return b

    def categorize(self) -> None:
        """Sorting incoming tags, matches them with blacklists, save result to self.args"""
        self.special_tags = [x for x in self.parsed_common_tags if x in anal_carnaval]
        self.restricted = [x for x in self.parsed_common_tags if x in not_ok]
        self.exclusion = [x for x in self.parsed_common_tags if x in tag_exeptions]

    @staticmethod
    def izvrat(donot: str) -> str:
        """convert result of searching restricted tags into joke error message
        to return it to user"""
        error_message_content = {
            'any_key': 'Your joke messages here'
        }
        if donot in error_message_content:
            return error_message_content[donot]

    def standart_filter(self) -> bool:
        """Raises custrom errors, based on types of restricted content.
        If no restricted tags found, returns False
        """
        if self.restricted:
            self.restricted = [self.get_by_value(x) for x in self.restricted]
            if not self.exclusion \
                    and not all([x == 'sex' for x in self.restricted]) \
                    and not self.special_tags:
                raise exceptions.Restricted(self.izvrat(self.restricted[0]))
            if self.special_tags:
                raise exceptions.SpecialContent
        elif self.special_tags:
            raise exceptions.SpecialContent
        else:
            return False

    def ignore_all_except_special(self) -> bool:
        """returns False if any types of restricted content strings found in self.parsed_common_tags,
        but named in anal_carnaval"""
        if self.special_tags:
            raise exceptions.SpecialContent
        else:
            return False

    def ignore_special(self) -> bool:
        """Returns False if only anal_carnaval restricted tags found"""
        if not self.restricted or self.exclusion:
            return False
        raise exceptions.Restricted(self.izvrat([self.get_by_value(x) for x in self.restricted][0]))

    def ignore_all(self) -> dict:
        """skips restricted content matching"""
        return self.parsed_common_tags

    def verdict(self) -> bool:
        """returns False if no filtering type was passed,
        else matching filtering type and returns result"""
        self.categorize()
        if self.filter_ignore:
            return getattr(self, self.filters[self.filter_ignore])()
        return False
