from __future__ import annotations

from itertools import chain
from typing import Iterator

from core.string_collector import StringCollector


def filter_input_by_value_and_blacklist(inputlist, blacklist):
    """filters given list by given blacklist and  length of values in given list"""
    return [x for x in inputlist if len(x) > 1 and x not in blacklist]


class CaptureEditor:
    def __init__(self, to_edit: dict | str, user_input: str):
        self.to_edit = to_edit
        self.user_input = user_input
        self.artist_marker = ['By:', '\nBy:', '\nBy', 'By']
        self.content_rate_tags = ['#ecchi', '#nude', '#sfw']
        self.sorted_input = {
            'tags': [],
            'artist': [],
            'fandom and char': []
        }
        self.collector = StringCollector()

    @property
    def to_edit(self):
        return self._to_edit

    @to_edit.setter
    def to_edit(self, value):
        self._to_edit = {
            'character': [],
            'artist': [],
            'fandom': [],
            'tags': []
        }
        for key in value:
            if value[key]:
                self._to_edit[key] = value[key]

    def artist_filter(self, splited_tags: list[str]) -> list[str]:  # separates userinput by variants of 'By'
        # then returns words without separator before them
        root = []
        if splited_tags[0] not in self.artist_marker:
            root = [splited_tags[0]]
        return root + [splited_tags[i] for i in range(1, len(splited_tags))
                       if splited_tags[i] not in self.artist_marker and splited_tags[i - 1] not in self.artist_marker]

    def possible_places_of_uncommon_lowercase_tags(self) -> list[str] | Iterator:  # since fandom and character fields
        # can contain both None and long snakecase hashtags (not simultaneously)
        fandom_and_char = [self.to_edit['character'], self.to_edit['fandom']]
        if all(fandom_and_char):
            return chain.from_iterable(fandom_and_char)
        else:
            general = []
            for pos in fandom_and_char:
                if pos:
                    general.extend(pos)
            return general

    def sort_input_by_categories(self) -> None:
        """method that takes the user_input string, splits it into a list of strings,
        and then sorts those strings into three
        different categories (artist, tags, and fandom and char) based on certain criteria
         (e.g., whether they appear after an "artist marker" string, whether they contain lowercase letters, etc.)."""
        splited = self.user_input.split(' ')
        without_artist = self.artist_filter(splited)
        self.sorted_input['artist'] = [x for x in splited if x not in self.artist_marker and x not in without_artist]
        possible_can_contain_lowercase = self.possible_places_of_uncommon_lowercase_tags()
        self.sorted_input['tags'] = [x for x in
                                     filter_input_by_value_and_blacklist(without_artist, possible_can_contain_lowercase)
                                     if x[1].islower() and x not in self.content_rate_tags]
        self.sorted_input['fandom and char'] = [x for x in
                                                filter_input_by_value_and_blacklist(without_artist,
                                                                                    self.sorted_input['tags'])
                                                if x[1].istitle() or x[1].islower()]

    def get_fandom_and_char_matches(self, key: str) -> list[str]:
        """Method that takes a key (either "fandom" or "character")
        and returns a list of strings that represent the intersection between
        the fandom and char list (from sorted_input) and the corresponding field in to_edit."""
        if not self.sorted_input['fandom and char'] or not self.to_edit[key]:
            return []
        else:
            return [x for x in self.sorted_input['fandom and char'] if x in self.to_edit[key]]

    def delete_matches(self) -> None:
        """Checks if any of the values of original capture match with the sorted_input values.
         If there are any matches, it removes the matching values
         from both the to_edit and sorted_input dictionaries."""
        for key in self.to_edit:
            if key == 'fandom' or key == 'character':
                matches = self.get_fandom_and_char_matches(key)
                if matches:
                    self.to_edit[key] = [x for x in self.to_edit[key] if x not in matches]
                    self.sorted_input['fandom and char'] = [x for x in self.sorted_input['fandom and char'] if
                                                            x not in matches]
            else:
                matches = [x for x in self.sorted_input[key] if x in self.to_edit[key]]
                if matches:
                    self.to_edit[key] = [x for x in self.to_edit[key] if x not in matches]
                    self.sorted_input[key] = [x for x in self.sorted_input[key] if x not in matches]

    def content_tag_replacer(self) -> None:
        """Checks if any of content tags in user input. If there are content rating tags, it adds content tag from user
        to common tags of capture (which prevents to default '#ecchi hastags to appear). Or if both input and
        original capture have content rating tags it replaces original capture content tag with content tag from user.
        Removes content rating tag from user input in both cases."""
        new_conent_tag = [x for x in self.content_rate_tags if x in self.user_input]
        old_content_tag = [x for x in self.to_edit['tags'] if x in self.content_rate_tags]
        if new_conent_tag and old_content_tag:
            self.to_edit['tags'] = new_conent_tag + [x for x in self.to_edit['tags'] if x not in self.content_rate_tags]
            self.user_input = self.user_input.replace(new_conent_tag[0], '')
        elif new_conent_tag:
            self.to_edit['tags'].extend(new_conent_tag)
            self.user_input = self.user_input.replace(new_conent_tag[0], '')

    def specific_key_add(self, key: str) -> None:
        """Appends the list of values of given key from the sorted_input dictionary to the
         corresponding key in the to_edit dictionary."""
        if key == 'fandom and char':
            self.to_edit['fandom'] += self.sorted_input['fandom and char']
        elif key == 'artist':
            self.to_edit['artist'] += self.sorted_input['artist']
        else:
            self.to_edit[key] += self.sorted_input[key]

    def add_new_tags(self) -> None:
        """Appends the list of values  from the sorted_input dictionary to the to_edit dictionary."""
        for key in self.sorted_input:
            if self.sorted_input[key]:
                self.specific_key_add(key)

    def to_string(self) -> str:
        """Returns values of self.to_edit dictionary as string throgh core.string_collector"""
        self.collector.tag_generator_result = self.to_edit
        return self.collector.to_string()

    def edit_by_user_input(self) -> dict[str | list]:
        """Splits string from user into tags, sorts them to cathegories based
        on whether they contain only lowercase letters, etc.
        Deletes intersections from sorted user input and previous capture, generated by bot in both dictionaries.
        If there any tags left - adds them to self.to_edit dictionary.
        Return self.to_edit dictionary."""
        self.content_tag_replacer()
        if len(self.user_input) > 0:
            self.sort_input_by_categories()
            self.delete_matches()
        if len(self.sorted_input.values()) > 0:
            self.add_new_tags()

        return self.to_edit
