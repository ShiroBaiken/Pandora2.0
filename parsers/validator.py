from __future__ import annotations


from bs4 import BeautifulSoup
from typing import Optional

from core import exceptions as error


# most of reverse search fails happens at the stage of request to sauce nao
# here is classes for handling these errors and support redirecting
# to yandex search engine if sauce nao wont find source links
# Each class below represents step of parsing links from SauceNao responce
# If epty value on stage affecting subsequent steps, special error rised

class SoupValidator:
    """Checks is whole page was parsed successfully"""
    def __init__(self):
        self.redirect_link: str = ''
        self._soup: Optional[BeautifulSoup] = None

    @property
    def soup(self):
        return self._soup

    @soup.setter
    def soup(self, value: BeautifulSoup):
        if value and len(value) == 0 \
                or 'error' in value:
            raise error.ErrorConnectToNAO
        else:
            self._soup = value


class TableValidator(SoupValidator):
    """Checks is connection was established and result have table"""
    def __init__(self):
        super(SoupValidator, self).__init__()
        self._sauce_table: Optional[list] = None

    @property
    def table(self):
        return self._sauce_table

    @table.setter
    def table(self, value: BeautifulSoup):
        if value and len(value) == 0:
            raise error.NoContentAtNAOPage
        else:
            self._sauce_table = value


class LinksToHighSimilarPicValidator(TableValidator):
    """checks presence of high similar results of search"""
    def __init__(self):
        super(TableValidator, self).__init__()
        self._links_to_high_similar_pic: Optional[list] = None

    @property
    def links_to_high_similar_pic(self):
        return self._links_to_high_similar_pic

    @links_to_high_similar_pic.setter
    def links_to_high_similar_pic(self, value: list):
        """
        Empty value at this stage isnt critical to whole process
        """
        self._links_to_high_similar_pic = value


class LinksToLessSimilarPicValidator(LinksToHighSimilarPicValidator):
    """check presence of less similar results of reverse search"""
    def __init__(self):
        super(LinksToLessSimilarPicValidator, self).__init__()
        self._links_to_less_similar_pic: list = []

    @property
    def links_to_less_similar_pic(self):
        return self._links_to_less_similar_pic

    @links_to_less_similar_pic.setter
    def links_to_less_similar_pic(self, value: list):
        if value is None or len(value) == 0:
            raise error.NoSimilarPics
        else:
            self._links_to_less_similar_pic = value


class ValidatorBuilder(LinksToLessSimilarPicValidator):
    def __init__(self):
        super(LinksToLessSimilarPicValidator, self).__init__()


class ReprForLinksSearch:
    def __init__(self, parsed_links: dict):
        self.parsed_links = parsed_links
        self.not_imageboards = ['twitter', 'deviantart']

    @property
    def parsable_imageboards(self) -> list:
        """Returns list of sites names which could be parsed"""
        return [x for x in self.parsed_links if x not in self.not_imageboards]

    def all_but_not_imageboards(self) -> bool:
        """Checks is sites what could be parsed has links in current SauseNao responce"""
        return any(x for x in self.parsable_imageboards
                   if self.parsed_links[x] is not None)

    def is_all_not_imageboards(self) -> bool:
        """Checks is only sites, what coudnt be parsed, has links in current SauseNao responce"""
        return all(self.parsed_links[x] for x in self.not_imageboards)

    def get_valide_not_imageboard(self) -> str:
        """returns list of sites names, which could be pased and have links in current SauseNao responce"""
        return [x for x in self.not_imageboards if self.parsed_links[x]][0]

    def str_repr_for_parsed_links(self) -> str | None:
        """converts result to human - readable str format for responce to user in chat"""
        if self.all_but_not_imageboards():
            for x in [(imageboard, link) for imageboard, link in self.parsed_links.items()
                      if link is not None and imageboard not in self.not_imageboards]:
                return None
        if self.is_all_not_imageboards():
            return f'I found only {self.not_imageboards[0]} and {self.not_imageboards[1]} links, sorry' \
                   f'\n{self.parsed_links[self.not_imageboards[0]]}' \
                   f'\n{self.parsed_links[self.not_imageboards[0]]}'
        else:
            valide = self.get_valide_not_imageboard()
            return f'I found only {valide}  link, sorry' \
                   f'\n{self.parsed_links[valide]}'
