from typing import Optional

"""This module turns capture lists into string, adds missing content rating tags and other decorations"""


class StringCollector:
    broken_nest_link = '\n' + '\n@brkennest'

    def __init__(self, tag_generator_result: Optional = None):
        self.tag_generator_result = tag_generator_result
        self.content_tags = ['#nude', '#sfw', '#ecchi']

    @staticmethod
    def swimsuit_filter(common_tags) -> list[str]:
        """This method prevents tags 'bikini' and 'swimsuit' to be plased in one string. \n
        Them offen comes together, but for illustration purposes
        it is assumed that a swimsuit means one-piece swimsuit"""
        return [tag for tag in common_tags if tag != "#swimsuit" or "#bikini" not in common_tags]

    def sorting(self, x) -> int:
        if x in self.content_tags:
            return 0
        else:
            return 1

    def nudity(self, common_tags: list[str]) -> list[str]:
        """
        This method sorts common tags

        :param common_tags: list[str] The common tags to filter

        :return: A list of strings, sorted to put content rating tags first
        """
        if not any(tag for tag in self.content_tags if tag in common_tags):
            common_tags.insert(0, '#ecchi')
        return sorted(common_tags, key=self.sorting)

    def common_hastags_filter(self, common_hastags) -> list[str]:
        """This method filters the common hashtags to exclude '#swimsuit' when '#bikini' is present,
         and puts content rating tags first"""
        swimsuit_check = self.swimsuit_filter(common_hastags)
        nudity_check = self.nudity(swimsuit_check)
        return nudity_check

    def artist_found_case(self, strings: list) -> None:
        """Adds a string of filtered common hashtags to the provided string list and appends the artist(s)"""
        string_of_tags = ' '.join(self.common_hastags_filter(self.tag_generator_result['tags']))
        strings.append(string_of_tags)
        strings.append('\nBy:')
        strings.append(' '.join(self.tag_generator_result['artist']))

    def artist_not_found_case(self, key: str, strings: list) -> None:
        """Appends the specified value in the provided key to the string list,
        followed by the filtered common hashtags and "By: ???"."""
        strings.append(' '.join(self.tag_generator_result[key]))
        string_of_tags = ' '.join(self.common_hastags_filter(self.tag_generator_result['tags']))
        strings.append(string_of_tags)
        strings.append('\nBy: ???')

    def standart_unpack_to_str(self) -> str:
        """Converts the fandom, character, filtered common hashtags, and artist
        into a string, formatted with each element separated by a space."""
        fandom = ' '.join(self.tag_generator_result['fandom'])
        character = ' '.join(self.tag_generator_result['character'])
        common_hastags = ' '.join(self.common_hastags_filter(self.tag_generator_result['tags']))
        artist = ' '.join(self.tag_generator_result['artist'])
        return f'{fandom} {character} {common_hastags} \nBy: {artist}'.strip()

    def only_valid_fields(self) -> str:
        """ Generates a string containing all non-empty fields of the
        tag generator's result."""
        not_empty = [x for x in self.tag_generator_result.keys() if self.tag_generator_result[x] and x != 'tags']
        string_list = []
        for key in not_empty:
            if key == 'artist':
                self.artist_found_case(string_list)
            elif not_empty.index(key) == len(not_empty) - 1:
                self.artist_not_found_case(key, string_list)
            else:
                string_list.append(' '.join(self.tag_generator_result[key]))
        return ' '.join(string_list).strip()

    def to_string(self) -> str:
        """Generates a string representation of the tag generator's result,
         followed by a newline character and the broken_nest_link."""
        if self.tag_generator_result is not str:
            if None not in self.tag_generator_result.values():
                return f'{self.standart_unpack_to_str()}{self.broken_nest_link}'
            else:
                return f'{self.only_valid_fields()}{self.broken_nest_link}'
        return f'{self.tag_generator_result}{self.broken_nest_link}'
