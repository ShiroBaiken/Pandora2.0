from __future__ import annotations

import numpy as np
from bson import ObjectId
from pymongo import MongoClient

from core.content_filter import ContentFilter

client = MongoClient('localhost', 27017)
db = client['BrokenNest']
nest_collection = db['nest']

hast = nest_collection.find_one({"_id": ObjectId("611274125f4ef8ffdd41cc2c")})

artists = nest_collection.find_one({"_id": ObjectId("6112818bf5e4af2eaeb88706")})

fandom = nest_collection.find_one({"_id": ObjectId("611281e209e6ef869b759faa")})

garbage = (
    'zelda (breath of the wild)', 'capcom', 'creatures (company)', 'game freak', 'original', 'square enix',
    'splatoon 2: octo expansion', 'splatoon 2', 'series', 'nintendo', 'metroid fusion', 'game', 'arms',
    'scorching-hot training', 'gainax', 'doujin', 'swimsuit mooncancer', 'titan', 'doodle', 'fbi', 'yordle',
    'illustration', 'doujin',
    "demon's whisper wraith", 'character request', 'character', 'kienzan', 'lapras', 'pervert',
    'original 1000+ bookmarks', 'palm bracelet', 'body chain', 'girl',
    'pixiv', 'one eye covered', 'original character', 'psg', 'Unknown')

"""Classes to convert parsed descriptions into interactive telegram hashtags.
For uniformity of results some parsed descriptions stored in database as keys and its values are complete hashtags.
Rest of parsed descriptions, which not stored in database, converted by scripts below.
"""

class TagGenerator:
    """Class to convert tags, gathered from imageboards, to interactive hashtags for telegram

        :args:
         database: dict, containing samples of parsed tags with hastags of it as values
         parsed_tags: dict with categorized tags, recived from ParsedInfoReducer (lists in values must be flat)
         recorded_in_bd: None: """
    def __init__(self, parsed_tags: dict, database: dict, recorded_in_bd: list = None, not_recorded: list = None):
        self.database: dict = database
        self.parsed_tags: dict = parsed_tags
        self.recorded_in_bd: list = recorded_in_bd
        self.not_recorded: list = not_recorded

    def categorize(self) -> TagGenerator:
        """
        sort incoming tags to 2 cathegories: ones, which recorder in database (actually, exactly keys in databse dict)
        and ones, which not
        :return:
        on succes, self.recorded_in_bd and\or self.not_recorded_in_bd filled with list of tags.
        returns self
        """
        if self.parsed_tags is not None:
            self.recorded_in_bd = [x for x in self.parsed_tags if x in self.database]
            self.not_recorded = [x for x in self.parsed_tags if x not in self.recorded_in_bd]
        return self

    def partial_categorize(self) -> TagGenerator:
        """pixiv has very diverse various of tags.
        To comply with the general view or results, only noted in database hashtags used,
        insted uf generating hashtags from not-recorded tags too."""
        self.recorded_in_bd = [x for x in self.parsed_tags if x in self.database]
        return self

    @staticmethod
    def capitalize_single_word(word) -> np.char:
        """returns capitalised single string if first char is not capital.
        Else returns incoming string"""
        if not word or np.char.istitle(word[0]):
            return word
        elif not np.char.istitle(word[0]):
            return np.char.capitalize(word)

    @staticmethod
    def snakecase_hashtag(word) -> np.char:
        """turns whitespaces in string to underscores"""
        chained = np.char.replace(word, ' ', '_')
        return chained

    @staticmethod
    def camelcase_hashtag(word) -> np.char:
        """Splits string by whitespace, capitalise each word and unite them back without whitespace,
        if only one whitespace in incoming string"""
        splited = np.char.split(word, ' ')
        arrayag = np.char.array(splited, unicode=True)
        camelcased = np.char.title(arrayag)
        return np.char.add(camelcased[0], camelcased[1])

    def snakecase_from_dash_hashtag(self, word) -> np.char:
        """turns dashes into underscores"""
        chained = np.char.replace(word, '-', '_')
        if ' ' not in chained:
            return chained
        else:
            chained_again = self.snakecase_hashtag(chained)
            return chained_again

    @staticmethod
    def replace_by_index(func_to_apply: callable, words: np.ndarray, axis: tuple) -> None:
        """
        Changes the elements in the array to the result by applying passed function along the index axis
        """
        for index in axis[0]:
            words[index] = func_to_apply(words[index])

    def change_dashes_to_snakecase(self, words: np.ndarray, number_of_dashes: np.array) -> None:
        """Applyes snakecase_from_dash_hashtag to array elements if array contains specifed items"""
        if np.count_nonzero(number_of_dashes) > 0:
            self.replace_by_index(self.snakecase_from_dash_hashtag, words,
                                  np.nonzero(number_of_dashes))

    def change_2_or_more_whitespaces_to_snakecase(self, words: np.ndarray, number_of_whitespaces: np.array) -> None:
        """Applyes snakecase_hashtag to array elements if array contains specifed items"""
        if np.any(number_of_whitespaces, where=2):
            self.replace_by_index(self.snakecase_hashtag, words,
                                  np.nonzero(number_of_whitespaces >= 2))

    def change_all_whitespaces_to_snakecase(self, words: np.ndarray, number_of_whitespaces: np.array) -> None:
        """Applyes snakecase_hashtag to array elements if array contains specifed items"""
        if np.any(number_of_whitespaces, where=1):
            self.replace_by_index(self.snakecase_hashtag, words,
                                  np.nonzero(number_of_whitespaces >= 1))

    def change_single_whitespace_words_to_camelcase(self, words: np.ndarray, number_of_whitespaces: np.array) -> None:
        """Applyes camelcase_hashtag to array elements if array contains specifed items"""
        if np.count_nonzero(number_of_whitespaces == 1) > 0:
            self.replace_by_index(self.camelcase_hashtag, words,
                                  np.nonzero(number_of_whitespaces == 1))

    def change_single_words_to_titled(self, words: np.ndarray, number_of_whitespaces: np.array,
                                      number_of_dashes: np.array) -> None:
        """Applyes capitalize_single_word to array elements if array contains specifed items"""
        if np.sum((number_of_whitespaces == 0) & (number_of_dashes == 0)) > 0:
            self.replace_by_index(self.capitalize_single_word, words, np.nonzero(number_of_whitespaces == 0))

    def hashtag_generator(self, words_to_convert_to_hashtags: list) -> list[str]:
        """Takes a list of parsed image descriptions and returns a list of hashtags generated from those.
        Convertion happens in following order:

        - The list of tags converted to a numpy array.
        - The number of whitespaces and dashes in each string are counted.
        - Strings with 2 or more whitespaces turned to snakecase.
        - Strings with dashes turned to snakecase.
        - Single-word strings are changed to titled case.
        - Changes single whitespace strings to camelcase.
        - Adds a "#" symbol to the beginning of each word and returns the resulting list as output.
        """
        str_array = np.array(words_to_convert_to_hashtags)
        number_of_whitespaces_per_word = np.char.count(str_array, ' ')
        number_of_dashes_per_word = np.char.count(str_array, '-')
        self.change_2_or_more_whitespaces_to_snakecase(str_array, number_of_whitespaces_per_word)
        self.change_dashes_to_snakecase(str_array, number_of_dashes_per_word)
        self.change_single_whitespace_words_to_camelcase(str_array, number_of_whitespaces_per_word)
        self.change_single_words_to_titled(str_array, number_of_whitespaces_per_word, number_of_dashes_per_word)
        return np.char.add('#', str_array).tolist()

    def lowercase_hastag_generator(self, words_to_convert_to_hashtags: dict) -> list[str]:
        """Takes a dictionary containing image descriptions that do not require camelcasing or capitalization,
         and generates a list of hashtags from those descriptions.

        The conversion process is as follows:

        - The list of words is converted to a numpy array.
        - The number of whitespaces and dashes in each string are counted.
        - Strings with whitespaces are turned to snakecase.
        - Strings with dashes are turned to snakecase.
        - All words are converted to lowercase.
        - A "#" symbol is added to the beginning of each word and returns the resulting list as output.
        """
        str_array = np.array(words_to_convert_to_hashtags)
        number_of_whitespaces_per_word = np.char.count(str_array, ' ')
        number_of_dashes_per_word = np.char.count(str_array, '-')
        self.change_all_whitespaces_to_snakecase(str_array, number_of_whitespaces_per_word)
        self.change_dashes_to_snakecase(str_array, number_of_dashes_per_word)
        return np.char.add('#', str_array).tolist()

    def create_hashtags_from_not_recognized_tags(self) -> None:
        """Returns a list of unuque stings, not saved in database, with self.hashtag_generator applyed"""
        self.not_recorded = [x for x in dict.fromkeys(self.hashtag_generator(self.not_recorded))]

    def create_hashtags(self) -> list[str]:
        """Returns list of unique hashtags, created from image descriptions,
        depending on how much of them are registered in database."""
        if self.recorded_in_bd and not self.not_recorded:
            return [x for x in dict.fromkeys([self.database[y] for y in self.recorded_in_bd])]
        elif self.recorded_in_bd and self.not_recorded:
            self.create_hashtags_from_not_recognized_tags()
            return [x for x in dict.fromkeys([self.database[y] for y in self.recorded_in_bd] + self.not_recorded)]
        elif self.not_recorded:
            self.create_hashtags_from_not_recognized_tags()
            return [x for x in dict.fromkeys(self.not_recorded)]


class ArtistTagGenerator(TagGenerator):
    def __init__(self, parsed_artist_tags: list[str], recorded_in_bd=None, not_recorded=None):
        super(ArtistTagGenerator, self).__init__(parsed_artist_tags, artists)

    def create_hashtags(self) -> list[str]:
        """Looks for artist's nicknames in artists database, if no mathes found, generates hashtags from them"""
        if self.recorded_in_bd:
            return list(set([self.database[x] for x in self.recorded_in_bd]))
        elif self.not_recorded:
            self.create_hashtags_from_not_recognized_tags()
            return list(set(self.not_recorded))
        else:
            pass


class TitleTagGenerator(TagGenerator):
    def __init__(self, parsed_title_tags, recorded_in_bd=None, not_recorded=None):
        super(TitleTagGenerator, self).__init__(parsed_title_tags, fandom)


class CharacterTagGenerator(TagGenerator):
    def __init__(self, parsed_charaters_tags, recorded_in_bd=None, not_recorded=None):
        super(CharacterTagGenerator, self).__init__(parsed_charaters_tags, hast)


class CommonTagsConvertor(TagGenerator):
    def __init__(self, parsed_common_tags, content_filter, tags=None):
        super(CommonTagsConvertor, self).__init__(parsed_common_tags, hast)
        self.content_filter = content_filter

    def categorize(self) -> CommonTagsConvertor:
        """Modified method of the parent class, aimed at processing only the tags contained in the database"""
        print(self.parsed_tags)  # tags from imageboards before database filter output to console to help add missing
        # tags and improve database
        self.recorded_in_bd = [x for x in self.parsed_tags if x in self.database]
        return self

    def create_hastags_from_all_tags(self) -> list[str]:
        return [x for x in dict.fromkeys(self.lowercase_hastag_generator(self.parsed_tags))]

    def create_hashtags(self) -> list | list[str] | bool:
        """Generates hashtags from parsed image descriptions.
        To avoid useless operations, here used ContentFilter, which looks up for special words in pre-processed tags.
        If those words present, it raises corresponding error, which prevents tags from processing and returns
        error message to pass it to telegram Message for user"""
        contentfilter = ContentFilter(self.parsed_tags, self.content_filter)
        verdict = contentfilter.verdict()
        if not verdict:
            return [x for x in dict.fromkeys([self.database[y] for y in self.recorded_in_bd])]
        elif isinstance(verdict, list):
            return self.create_hastags_from_all_tags()
        else:
            return verdict


class PixivCommonTagGenerator(TagGenerator):
    def __init__(self, parsed_tags: dict):
        super().__init__(parsed_tags, hast)
        self.output_copy = dict.fromkeys(self.parsed_tags)

    def recognize_and_generate_hashtags(self, content_filter_value) -> dict:
        """Whole process of turn parsed image descriptions, but designed for results from pixiv.
        It uses less categories and only tags, recorded in database, will be processed.
        Also, ContentFilter, which raises corresponding errors
        if special words occur in parsed tags, used here as well.
        Returns result as dict, with same keys as assumed input.
        """
        content_filter = ContentFilter(self.parsed_tags, content_filter_value)
        if not content_filter.verdict():
            self.output_copy['character'] = CharacterTagGenerator(self.parsed_tags['tags']) \
                .partial_categorize().create_hashtags()
            self.output_copy['fandom'] = TitleTagGenerator(self.parsed_tags['tags']) \
                .partial_categorize().create_hashtags()
            common_tags = [x for x in self.parsed_tags['tags'] if x not in self.parsed_tags['character'] and
                           x not in self.parsed_tags['fandom']]
            self.output_copy['tags'] = CommonTagsConvertor(common_tags, 'already used')
            self.output_copy['artist'] = self.parsed_tags['artist']
            return self.output_copy


class TagGeneratorHandler:
    def __init__(self, parsed_tags: dict, filter_value: str = 'standart'):
        self.filter_value = filter_value
        self.parsed_tags = parsed_tags
        self.output_copy = dict.fromkeys(self.parsed_tags)

    def recognize_and_generate_hasttags(self) -> dict:
        """This method converts image descriptions into hashtags in all categories.
        If 'pixiv' string in common tags category (added by parser, if Pixiv was only awailible sourse of picture),
        PixivCommonTagGenerator used for hashtags generation.
        Else used TagGenerator classes, coressponding to category, started from common tags, with build-in ContentFilter
        which raises errors if special tags occurs in parsed pic description.
        """
        if 'pixiv' in self.parsed_tags['tags']:
            return PixivCommonTagGenerator(self.parsed_tags).recognize_and_generate_hashtags(self.filter_value)
        else:
            self.output_copy['tags'] = CommonTagsConvertor(self.parsed_tags['tags'], self.filter_value). \
                categorize().create_hashtags()
            self.output_copy['artist'] = ArtistTagGenerator(self.parsed_tags['artist']) \
                .categorize().create_hashtags()
            self.output_copy['fandom'] = TitleTagGenerator(self.parsed_tags['fandom']) \
                .categorize().create_hashtags()
            self.output_copy['character'] = CharacterTagGenerator(self.parsed_tags['character']) \
                .categorize()\
                .create_hashtags()
        return self.output_copy





