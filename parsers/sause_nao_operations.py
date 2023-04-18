from __future__ import annotations

import typing
from abc import ABC, abstractmethod
from collections.abc import Iterable
from io import BytesIO

import bs4
import requests as req
from bs4 import BeautifulSoup as bs, BeautifulSoup

from core.exceptions import ErrorConnectToNAO

links_to_imageboards = {
    'yande.re': None,
    'pixiv': None,
    'twitter': None,
    'gelbooru': None,
    'danbooru': None,
    'thatpervert': None,
    'reactor': None,
    'rule34': None,
    'chan.sankaku': None,
    'xbooru': None,
    'anime-pictures': None,
    'deviantart': None,
    'creator': None,
}


class Parser(ABC):
    @abstractmethod
    def get_soup(self):
        pass


class SauseNaoParser:

    def __init__(self, file, session, parsed_links=None):
        self.info: list = []
        self.file_path: str | BytesIO = file
        self.parsed_links: dict = parsed_links
        self.session: req.Session = session

    @staticmethod
    def open_local_html(path: str) -> bytes:
        """Static method that reads an HTML file from the local filesystem and returns its contents as bytes."""
        with open(path, 'rb') as f:
            return f.read()

    def get_soup(self) -> BeautifulSoup:  # parses whole html page.
        """Sends an HTTP POST request to saucenao.com with the image file attached,
        then parses the resulting HTML with BeautifulSoup."""
        reverse_search_url = 'http://saucenao.com/search.php'
        file = {'file': ('1.jpg', self.file_path, 'image/jpg')}
        response = self.session.post(reverse_search_url, files=file, allow_redirects=True)
        nao_soup = bs(response.content, 'lxml')
        return nao_soup

    @staticmethod
    def get_redirection_link(soup: BeautifulSoup) -> str:
        """Extracts a redirection link from the search result page,
        which points to Yandex image search engine."""
        if type(soup) == 'NoneType':
            raise ErrorConnectToNAO
        elif soup.find(class_='resulttablecontent') is None:
            raise ErrorConnectToNAO
        else:
            redirection_links = soup.find(id='yourimageretrylinks').find_all('a')
            to_yandex = redirection_links[5].get('href')
            return to_yandex

    @staticmethod
    def get_table(nao_soup: BeautifulSoup) -> list[bs4.PageElement]:
        """Extracts the relevant parts of the HTML search result page
        (such as links to image sources and the similarity score)
        and returns them as a list of bs4.PageElement objects. \n
          BeautifoulSoup Object --> list[PageElement, ...]"""
        try:
            point_of_unrelevant_links = nao_soup.find(class_="result hidden")
        except Exception as e:
            return []
        if point_of_unrelevant_links:
            valid_result_cells = [x.extract() for x in
                                  point_of_unrelevant_links.findAllPrevious(attrs={'class': 'resulttablecontent'})]
            return valid_result_cells[::-1]
        else:
            return [x.extract() for x in nao_soup.findAll(attrs={'class': 'resulttablecontent'})]

    def save_named_link(self, imageboard_name: str, url: str,
                        link_text: typing.Optional[str] = None) -> None:
        """Saves a URL to the parsed_links dictionary if it matches a imageboard name,
        specifed in links_to_imageboards"""
        link_text = url if link_text is None else link_text
        link_subscription = str(link_text).lower()
        if imageboard_name not in link_subscription:
            pass
        elif imageboard_name == 'pixiv' and 'member.php' in link_subscription:
            # sometimes link from site leads to artist's profile
            # instead of post
            pass
        else:
            self.parsed_links[imageboard_name] = url

    @staticmethod
    def get_similarity_procent(html_soup: BeautifulSoup) -> str:
        """get value of similarity (as a percentage) between result and searched image"""
        return html_soup.find(class_="resultsimilarityinfo").text.strip('%')

    @staticmethod
    def get_links_from_sause_nao_soup(html_soup: BeautifulSoup, html_class: str) -> list:
        """Extracts links from the HTML page that match a specific html class"""
        soup_with_link = html_soup.find(class_=html_class)
        links = soup_with_link.find_all('a')
        urls = []
        for url in links:
            if hasattr(url, 'href'):
                urls.append(url.get('href'))
        return urls

    def pack_links_and_similarity_from_result_to_tuple(self, html_soup: BeautifulSoup) -> tuple:
        """Extracts the similarity score and all links from a single search result, and returns them as a tuple."""
        similarity = float(self.get_similarity_procent(html_soup))
        links_from_desc = self.get_links_from_sause_nao_soup(html_soup, 'resultmiscinfo')
        links_from_corner = self.get_links_from_sause_nao_soup(html_soup, 'resultcontentcolumn')
        check_list = [similarity, *links_from_desc, *links_from_corner]
        return tuple([x for x in check_list if x is not None])

    def get_high_similar_results(self, html_soup: BeautifulSoup) -> list:
        """Returns a list of tuples containing links from search results
         with a similarity score greater than or equal to 87%."""
        soup_with_high_similarity = [x for x in html_soup if float(self.get_similarity_procent(x)) >= 87]
        return [x for x in list(map(self.pack_links_and_similarity_from_result_to_tuple, soup_with_high_similarity)) if
                len(x) > 1]

    def get_less_similar_results(self, html_soup: BeautifulSoup) -> list:
        """Returns a list of tuples containing links
         from search results with a similarity score less or equal to 87%."""
        soup_with_less_similarity = [x for x in html_soup if float(self.get_similarity_procent(x)) <= 87]
        return [x for x in list(map(self.pack_links_and_similarity_from_result_to_tuple, soup_with_less_similarity)) if
                len(x) > 1]

    def save_links_to_imageboards(self, imageboards: list, link: str) -> None:
        """Saves a URL to the parsed_links dictionary if it matches any of the given imageboard names."""
        for imageboard in imageboards:
            self.save_named_link(imageboard, link)

    def parse_links_from_single_result(self, imageboards: list, links: tuple) -> None:
        """Saves URL from a tuple with single search result to self.parsed_links."""
        for link in links[1:]:
            self.save_links_to_imageboards(imageboards, link)

    def parse_links_to_imageboards(self, list_of_links: Iterable[tuple], imageboards: dict) -> None:
        """Saves all URLs from given list with tuples of results to self.parsed_links"""
        for links_tuple in list_of_links:
            imageboards_names = [x for x in imageboards.keys() if imageboards[x] is None]
            self.parse_links_from_single_result(imageboards_names, links_tuple)

    def parsed_links_count(self) -> int:
        """Returns the number of parsed links in the parsed_links dictionary."""
        return len([x for x in self.parsed_links.values() if x is not None])


class NAOArtistParser:
    filterlist: typing.ClassVar = ('Member: ', 'Creator(s): ', 'Author: ', 'Creator: ')

    def __init__(self, nao_parser: SauseNaoParser, artist: list):
        self.nao_parser = nao_parser
        self.artist = artist

    def artist_filter(self, bs_element) -> bool | bs4.PageElement:
        """detects presence of html elements which can contain artist's nicname and return
         named elements if them present"""
        if bs_element and len(bs_element.contents) > 0:
            return str(bs_element.contents[0]) in self.filterlist
        else:
            return False

    @staticmethod
    def get_artist_name(artist_desc: bs) -> str:
        """parses artist nickname from html element"""
        if not artist_desc:
            pass
        if hasattr(artist_desc.next_sibling, 'href'):
            return str(artist_desc.next_sibling.get_text())
        else:
            return str(artist_desc.next_sibling)

    @staticmethod
    def get_artists_from_title(table_cell_info: BeautifulSoup) -> list[bs4.NavigableString]:
        """Get artists nicknames from specific part of Sauce NAO result table"""
        try:
            titles = table_cell_info.find(class_="resulttitle").strong
        except AttributeError:
            titles = []
        return titles

    @staticmethod
    def get_artists_fron_desc(table_cell_info: BeautifulSoup) -> list[bs4.NavigableString]:
        """Get artists nicknames from specific part of Sauce NAO result table"""
        try:
            desc_tag = table_cell_info.find(class_="resultcontentcolumn").findAll('strong')
        except AttributeError:
            desc_tag = []
        return desc_tag

    def get_artists(self, parsed_table_info: list[BeautifulSoup]) -> Iterable[str | None]:
        """Returns list of artist's nicknames, found in SauceNAO result"""
        titles = map(self.get_artists_from_title, parsed_table_info)
        descripions = map(self.get_artists_fron_desc, parsed_table_info)
        names = []
        if titles:
            artists_from_title = (x for x in filter(self.artist_filter, titles) if len(x) > 0)
            names = [self.get_artist_name(x) for x in artists_from_title]
        if descripions:
            artists_from_desc = (x for x in filter(self.artist_filter,
                                                   [x for y in descripions for x in y]) if len(x) > 0)
            names += [self.get_artist_name(x) for x in artists_from_desc]

        return names
