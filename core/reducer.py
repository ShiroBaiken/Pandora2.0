from __future__ import annotations

from functools import partial
from itertools import chain
from typing import Callable

import numpy as np
import pandas as pd
from rapidfuzz.distance import Indel

from core.exceptions import UnsuccefulParsing
from core.pre_reduce_filter import ReducerFilter, ReduceMethod, PositionalReduce
from core.tag_generator import garbage

"""Family of classes to exclude empty results from parsed file descriptions and apply corresponding method of
flatten lists with descriptions, based on how much sites with descriptions were succefuly parsed 
and type of descriptions list"""

class ParsedInfoReducer:

    @staticmethod
    def parsed_to_array(parsed: list[list[str]]) -> np.array:
        """prepare lists from imageboards to be converted into numpy array"""
        framed = pd.DataFrame(parsed)
        filled = framed.fillna('').values
        return filled

    @staticmethod
    def levenstein_based_choice(artists_nicks: list[str]) -> list[str]:
        for sample in artists_nicks:
            for nickname in [x for x in artists_nicks if x != sample]:
                if Indel.normalized_similarity(sample, nickname) > 0.78:
                    return [sample]

    def similar_or_first_nickname(self, nicknames: list[str]) -> list:
        similar_nick_in_nicknames = self.levenstein_based_choice(nicknames)
        if not similar_nick_in_nicknames:
            return [nicknames[0]]
        if similar_nick_in_nicknames:
            return similar_nick_in_nicknames

    @staticmethod
    def flat_to_at_least_two_times_per_unique(uniques: list[str], array_of_tags: np.array) -> list[str]:
        return [x for x in uniques if np.count_nonzero(array_of_tags == x) >= 2]

    @staticmethod
    def original_order(original: list[str], word: str) -> int:
        for original_word in original:
            if word in original_word:
                return original.index(original_word)

    def sort_in_original_order(self, original: list[str], sortable: list[str]) -> list[str]:
        sorter = partial(self.original_order, original)  # sorting func saved as var
        indexes = list(map(sorter, sortable))  # indexes of original list
        return [x[1] for x in sorted(zip(indexes, sortable))]

    @staticmethod
    def open_brackets(subscriptions_with_brackets: list[str]) -> object | list:
        if subscriptions_with_brackets:
            chararr = np.array(subscriptions_with_brackets, dtype=str)
            right_braket_stripped = np.char.strip(chararr, ')')
            split_by_bracket = np.char.split(right_braket_stripped, '(')
            flatten = np.concatenate(split_by_bracket).ravel()
            return np.char.rstrip(flatten, ' ').tolist()
        else:
            return []  # this makes able to add result no matter of its context

    def add_subscriptions_from_brackets(self, reduced_subscriptions: list[str]) -> list[str]:
        without_brackets = [x for x in reduced_subscriptions if '(' not in x]
        with_brackets = [x for x in reduced_subscriptions if '(' in x]
        opened = self.open_brackets(with_brackets)

        united = [x for x in dict.fromkeys(without_brackets + opened)]
        return self.sort_in_original_order(reduced_subscriptions, united)

    def single_result_handler(self, single_result: list[list[str]]) -> list[str]:
        with_brackets = [x for x in single_result[0] if '(' in x]
        if with_brackets:
            return self.add_subscriptions_from_brackets(single_result[0])
        else:
            return single_result[0]

    @staticmethod
    def choice_between_two(subscriptions: list[list[str]]) -> list:
        if 'pixiv' not in dict.fromkeys(chain.from_iterable(subscriptions)):
            return sorted(subscriptions, key=len, reverse=True)[0]

    def generic_method(self, fandom_position: list[list[str]]) -> list[str]:
        subscriptions_array = self.parsed_to_array(fandom_position)
        uniques = [x for x in dict.fromkeys(chain.from_iterable(fandom_position)) if x != '']
        without_brackets = self.get_list_without_brackets(uniques)
        if len(uniques) == len(without_brackets):
            reduced = self.flat_to_at_least_two_times_per_unique(uniques, subscriptions_array)
            return reduced
        else:
            reduced_with_brackets_open = self.add_subscriptions_from_brackets(
                self.flat_to_at_least_two_times_per_unique(uniques, subscriptions_array))
            return reduced_with_brackets_open

    @staticmethod
    def get_list_without_brackets(uniques: list) -> list[str]:
        if not uniques:
            return []
        else:
            return [x for x in filter(lambda x: x is True, uniques) if '(' not in x]

    def artist_reduce_check(self, uniques: list,
                            array: np.array, reduced: list[str]) -> list[str]:
        if len(reduced) == 0:
            return self.levenstein_based_choice(uniques)
        else:
            if len(set(map(lambda x: x.lower(), reduced))) > 1:
                return reduced
            return [x for x in reduced if np.count_nonzero(array == x)
                    == max([np.count_nonzero(array == x) for x in uniques])]

    def optional_levenshtein_clean_position(self, artist_position: list[list]) -> list:
        subscriptions_array = self.parsed_to_array(artist_position)
        uniques = [x for x in dict.fromkeys(chain.from_iterable(artist_position)) if x and x != '' and x != 'Unknown']
        without_brackets = [x for x in uniques if '(' not in x]
        if len(uniques) == len(without_brackets):
            reduced = self.flat_to_at_least_two_times_per_unique(uniques, subscriptions_array)
        else:
            reduced = self.add_subscriptions_from_brackets(
                self.flat_to_at_least_two_times_per_unique(uniques, subscriptions_array))
        return self.artist_reduce_check(uniques, subscriptions_array, reduced)

    @staticmethod
    def dynamic_fandom_filter(output: dict) -> list | None:
        if output['fandom'] is None:
            return None
        else:
            blacklist = [x for x in garbage]
            blacklist.extend(output['fandom'])
            return blacklist

    @staticmethod
    def try_complicated(reduce_args: dict[str, ReduceMethod], pos_name: str, pos_val: list) -> list[str]:
        pos_red = PositionalReduce(reduce_args[pos_name], pos_val)
        return pos_red.reduce()

    def reduce_all(self, parsed_positions: dict) -> dict:
        reduce_args = {
            'artist': ReduceMethod(self.single_result_handler, self.optional_levenshtein_clean_position),
            'fandom': ReduceMethod(self.single_result_handler, self.optional_levenshtein_clean_position),
            'character': ReduceMethod(self.single_result_handler, self.generic_method),
            'tags': ReduceMethod(self.single_result_handler, self.generic_method,
                                 special=self.choice_between_two, condition=lambda x: len(x) <= 2)
        }
        reduce_result = {'fandom': None}
        for position, val in parsed_positions.items():
            positional_args = {
                'artist': garbage,
                'fandom': garbage,
                'character': self.dynamic_fandom_filter(reduce_result),
                'tags': garbage
            }
            reduce_result[position] = ReducerFilter().optional_filter(self.try_complicated(reduce_args, position, val),
                                                                      positional_args[position])
        if not any([reduce_result[x] for x in reduce_result if x != 'artist']):
            raise UnsuccefulParsing
        return reduce_result


sample = {
    'artist': [['dishwasher1910'], ['']],
    'character': [['gojou satoru']],
    'fandom': [['jujutsu kaisen']],
    'tags': [['breasts',
              'genderswap',
              'nipples',
              'no bra',
              'nopan',
              'open shirt',
              'pussy',
              'uncensored'],
             ['']]
}

if __name__ == '__main__':
    reducer = ParsedInfoReducer()
    reducer.reduce_all(sample)
