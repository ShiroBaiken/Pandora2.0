from __future__ import annotations

import typing

import asyncio
import dataclasses
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields
from os import environ as venv
from string import printable

import httpx
from bs4 import BeautifulSoup as bs, BeautifulSoup
from pixivpy_async import AppPixivAPI, PixivClient

imageboards_html_tags = {  # flags for parsing, see Imageboard Parser below for more info
    'Booru': {
        'fandom': {'class': "tag-type-copyright"},
        'artist': {'class': "tag-type-artist"},
        'character': {'class': "tag-type-character"},
        'tags': {'class': "tag-type-general"}
    },
    'Danbooru': {
        'fandom': {'class': "copyright-tag-list"},
        'artist': {'class': "artist-tag-list"},
        'character': {'class': "character-tag-list"},
        'tags': {'class': "general-tag-list"}
    },

    'Rule34': {
        'fandom': {'class': "copyright-tag"},
        'artist': {'class': "artist-tag"},
        'character': {'class': "character-tag"},
        'tags': {'class': "general-tag"}
    },
    'AnimePictures': {
        'fandom': {'copyright': True, 'pictures': True, 'tag': True, 'with': True},
        'artist': {'artist': True, 'pictures': True, 'tag': True, 'with': True},
        'character': {'character': True, 'pictures': True, 'tag': True, 'with': True},
        'tags': {
            'href': True, 'artist': False, 'character': False,
            'copyright': False, 'pictures': True, 'tag': True,
            'with': True
        },
    }
}


class ABC_Imageboard_Parser(ABC):
    """
    This is the skeleton of a template for parsing an imageboards according to the following scheme:
    first, the entire htmlcode from the page with the requested picture is obtained,
    then it is disassembled into more specific parts
    through cycles until left only tags from the description of the picture.
    """

    @abstractmethod
    def get_soup(self, session) -> BeautifulSoup:
        pass

    @abstractmethod
    async def async_get_soup(self, session: any) -> BeautifulSoup:
        pass

    @staticmethod
    @abstractmethod
    def parse_category_soup_fragmets(soup: BeautifulSoup, name: str, position: str) -> list[BeautifulSoup]:
        pass

    @property
    @abstractmethod
    def parsing_attrs_names(self) -> list:
        pass

    @abstractmethod
    def extract_soup_to_attrs(self, soup: BeautifulSoup) -> None:
        pass

    @abstractmethod
    def description_cleaner(self, bs_with_tag: BeautifulSoup) -> list[str]:
        pass

    @abstractmethod
    def remove_all_unnesessary_parsed_info(self) -> None:
        pass


@dataclass
class ImageboardParser(ABC_Imageboard_Parser):  # tags from picture description separated by groups:
    url: any = field(repr=False)
    fandom: list = field(default=None, init=False)  # series/movie/etc where character on the picture from
    artist: list = field(default=None, init=False)  # creator of picture
    character: list = field(default=None, init=False)  # charater(s) on pic
    tags: list = field(default=None, init=False)  # various details like clothing and etc

    def get_soup(self, session: any) -> BeautifulSoup:
        """returns whole html of source page
        depricated sync method"""
        link = self.url
        responce_text = session.get(link, verify=False).text
        soup = bs(str(responce_text), features='lxml')
        return soup

    async def async_get_soup(self, session: any) -> BeautifulSoup:
        """returns whole html of page asynchronously"""
        responce = await session.get(self.url)
        return bs(responce.text, features='lxml')

    @staticmethod
    def get_soup_from_file(file: bytes) -> BeautifulSoup:
        """method for local files"""
        soup = bs(file, features='lxml')
        return soup

    @staticmethod
    def parse_category_soup_fragmets(soup: BeautifulSoup, name: str, position: str) -> list[BeautifulSoup]:
        """ Get soup fragments for category, specifed in init. \n
         Values of imageboards_html_tags used here as args for BeautifulSoup.findAll. \n
         Exactly structure of html may be different for various sites
         but 'gelbooru' scheme is most common, so it used as basic scheme"""
        if name not in imageboards_html_tags:
            new_name = 'Booru'
        else:
            new_name = name
        return [x.extract() for x in soup.findAll(attrs=imageboards_html_tags[new_name][position])]

    @property
    def parsing_attrs_names(self) -> list:
        """returns names of args used as cathegories in list"""
        return [x.name for x in fields(self) if x.name != 'url']

    def remove_all_unnesessary_parsed_info(self) -> None:
        """Iterate through cathegories to clean up parsed data"""
        for attr_name in [x for x in self.parsing_attrs_names if x in vars(self)]:
            self.description_cleaner(vars(self)[attr_name])


@dataclass
class BooruParser(ImageboardParser):

    def fill_class_attributes(self, session) -> None:
        """Depricated synchronous method, can be used for debugging. \n
        Stores parts of html to cathegories attrs"""
        soup = self.get_soup(session)
        self.tags = [x.extract() for x in soup.findAll(attrs={'class': "tag-type-general"})]
        self.artist = [x.extract() for x in soup.findAll(attrs={'class': "tag-type-artist"})]
        self.fandom = [x.extract() for x in soup.findAll(attrs={'class': "tag-type-copyright"})]
        self.character = [x.extract() for x in soup.findAll(attrs={'class': "tag-type-character"})]

    def extract_soup_to_attrs(self, soup: BeautifulSoup) -> None:
        """Stories parts of html to cathegories attrs"""
        attrs = self.parsing_attrs_names
        for pos in attrs:
            setattr(self, pos, self.parse_category_soup_fragmets(soup, self.__class__.__name__, pos))

    def booru_stripper(self, bs_with_tag) -> str:
        """Turns raw text from link into tag"""
        parsed_tag_text = bs_with_tag.text
        question_mark_removed = parsed_tag_text.split(' ', maxsplit=1)
        tag_body = question_mark_removed[1].rsplit(' ', maxsplit=2)[0]
        return tag_body

    def description_cleaner(self, attribute_val: list[BeautifulSoup | bs.NavigableString]) -> None:
        """Replaces soup fragments in cathegory
         to clean description tags"""
        for i in range(len(attribute_val)):
            attribute_val[i] = self.booru_stripper(attribute_val[i])


@dataclass
class Pixiv(ImageboardParser):
    """Unlike other parsers, this one using special api
    and recives json instead of soup
    so the part of basic methods is useless
    but still implemente, which allows to use it as other parsers
    and avoid errors"""

    def description_cleaner(self, bs_with_tag) -> None:
        return None

    def id_get(self) -> int:
        """Gets id of post on pixiv"""
        # liks to pixiv may be in 2 different forms
        if '=' in self.url:
            splited_url = self.url.rsplit('=')
            if len(splited_url) >= 3:
                post_id = splited_url[2]
                return post_id
            else:
                pass
        else:
            splited_url = self.url.rsplit('/', maxsplit=1)
            return splited_url[1]

    async def async_get_soup(self, session: any) -> dict:
        """gets json from API"""
        async with PixivClient() as client:
            api = AppPixivAPI(client=client)
            await api.login(refresh_token=venv['PIXIV_TOKEN'])
            result = await api.illust_detail(self.id_get())
            return result

    @staticmethod
    def pixiv_artist(illust_detail) -> list[str]:
        """Gets artist's nickname"""
        artist = []
        artist_name = illust_detail['name']
        with open(venv['PIXIV_ARTISTS'], 'r', encoding='utf-8') as file:
            pixiv_base = json.load(file)
        if artist_name in pixiv_base['artists']:
            artist.append(pixiv_base['artists'][artist_name])
        else:
            artist.append(artist_name)
        return artist

    @staticmethod
    def is_latin(text):
        """Checks is sting contains hieroglyphs."""
        return not bool(set(text) - set(printable))

    def get_only_english_tags(self, tag):
        """Since async API logs at japanase version and pixiv \n
        has no strong pattern for tags there is can be both
        english and japanase tags under same post. \n
        Hieroglyphs doesn't recognised by bot"""
        is_latin_name = self.is_latin(tag['name'])
        if not is_latin_name and not tag['translated_name']:
            return False
        elif is_latin_name and not tag['translated_name']:
            return tag['name']
        elif tag['translated_name']:
            return tag['translated_name']

    def pixiv_tags(self, result) -> list[str]:
        """Gets various, unsorted tags from post, \n
        because pixiv doesn't have inner structure of categories of tags"""
        tags = []
        try:
            illust_detail = result['illust']['tags']
            for tag in illust_detail:
                check = self.get_only_english_tags(tag)
                if check is not False:
                    tags.append(check.lower())
            if tags:
                tags.append('pixiv')
        except KeyError:
            return ['']
        return [x for x in tags if '+ bookmarks' not in x]

    def extract_soup_to_attrs(self, result: dict):
        """Stores parsed tags to class attrs"""
        # sauce nao often provides expired links to pixiv,
        # which usually causes an error if you dont handle it
        if 'error' not in result:
            self.tags = self.pixiv_tags(result)
            self.artist = self.pixiv_artist(result['illust']['user'])
        else:
            self.tags = ['']
            self.artist = ['']


@dataclass
class Gelbooru(BooruParser):

    def booru_stripper(self, bs_with_tag: BeautifulSoup) -> str:
        """Turns raw text from link into tag"""
        parsed_tag_text = bs_with_tag.text
        digits_removed = parsed_tag_text.rsplit(' ', maxsplit=1)
        question_mark_removed = digits_removed[0]
        pre_tag_body = question_mark_removed.split('\n', maxsplit=4)[-1]
        tag_body = pre_tag_body.split(' ', maxsplit=1)[-1]
        return tag_body


@dataclass
class Danbooru(BooruParser):

    def fill_class_attributes(self, session: any) -> None:
        soup = self.get_soup(session)
        self.tags = [[x.extract() for x in soup.findAll(attrs={'class': "general-tag-list"})][1]]
        self.artist = [[x.extract() for x in soup.findAll(attrs={'class': "artist-tag-list"})][1]]
        self.fandom = [[x.extract() for x in soup.findAll(attrs={'class': "copyright-tag-list"})][1]]
        self.character = [[x.extract() for x in soup.findAll(attrs={'class': "character-tag-list"})][1]]

    def original_character_case(self, cathegory: str, fragments: list):
        """Original characters in new markup belongs to another part of html-three"""
        if len(fragments) > 1:
            setattr(self, cathegory, [fragments[1]])
        else:
            setattr(self, cathegory, [])

    def extract_soup_to_attrs(self, soup: BeautifulSoup) -> None:
        for attr_name in self.parsing_attrs_names:
            soup_fragments = self.parse_category_soup_fragmets(soup, self.__class__.__name__, attr_name)
            self.original_character_case(attr_name, soup_fragments)

    def description_cleaner(self, attribute_val: list) -> None:
        """Turns raw text from links into tags"""
        output = []
        if attribute_val:
            titles = attribute_val[0].findAll('li')
            if len(titles) > 0:
                for title in titles:
                    text = title.find(class_='search-tag').text
                    output.append(text)
        attribute_val.clear()
        attribute_val.extend(output)


@dataclass
class Yandere(BooruParser):
    def __init__(self, url):
        super(Yandere, self).__init__(url)

    def booru_stripper(self, bs_with_tag: BeautifulSoup) -> str:
        """Turns raw text from links into tags"""
        soup_fragment_with_tag = bs_with_tag.find('a').find_next('a')
        if soup_fragment_with_tag:
            tag_body = soup_fragment_with_tag.get_text().strip()
            return tag_body


@dataclass
class Sankaku(BooruParser):
    def __init__(self, url):
        super(Sankaku, self).__init__(url)

    def booru_stripper(self, bs_with_tag: BeautifulSoup) -> str:
        """Turns raw text from links into tags"""
        tag_body = bs_with_tag.find('a').get_text().strip()
        return tag_body


@dataclass
class AnimePictures(BooruParser):
    def __init__(self, url):
        super(AnimePictures, self).__init__(url)

    def fill_attributes(self, session) -> None:
        soup = self.get_soup(session)
        self.tags = [x.extract() for x in soup.findAll(
            attrs={
                'href': True, 'artist': False, 'character': False, 'copyright': False, 'pictures': True, 'tag': True,
                'with': True
            })]
        self.artist = [x.extract() for x in
                       soup.findAll(attrs={'artist': True, 'pictures': True, 'tag': True, 'with': True})]
        self.fandom = [x.extract() for x in
                       soup.findAll(attrs={'copyright': True, 'pictures': True, 'tag': True, 'with': True})]
        self.character = [x.extract() for x in
                          soup.findAll(attrs={'character': True, 'pictures': True, 'tag': True, 'with': True})]

    def description_cleaner(self, attribute_val) -> None:
        """Turns raw text from links into tags"""
        for i in range(len(attribute_val)):
            attribute_val[i] = attribute_val[i].text


@dataclass
class Rule34(BooruParser):
    def __init__(self, url):
        super(Rule34, self).__init__(url)

    def fill_class_attributes(self, session: any) -> None:
        soup = self.get_soup(session)
        self.tags = [x.extract() for x in soup.findAll(attrs={'class': "general-tag"})]
        self.artist = [x.extract() for x in soup.findAll(attrs={'class': "artist-tag"})]
        self.fandom = [x.extract() for x in soup.findAll(attrs={'class': "copyright-tag"})]
        self.character = [x.extract() for x in soup.findAll(attrs={'class': "character-tag"})]

    def booru_stripper(self, bs_with_tag: BeautifulSoup):  # part of parsed soup fragments somehow is empty
        try:
            tag_body = bs_with_tag.a.get_text().strip()
            if tag_body != 'Flag for Deletion' or tag_body != '':
                return tag_body
            else:
                pass
        except AttributeError:
            pass

    def description_cleaner(self, attribute_val: list[BeautifulSoup]) -> None:
        output = []
        for i in range(len(attribute_val)):
            tag = self.booru_stripper(attribute_val[i])
            if tag is not None and tag != '' and tag != 'Flag for Deletion':
                output.append(tag)
        attribute_val.clear()
        attribute_val.extend(output)


@dataclass
class Xbooru(BooruParser):
    def __init__(self, url):
        super(Xbooru, self).__init__(url)

    def booru_stripper(self, bs_with_tag: BeautifulSoup):
        tag_body = bs_with_tag.a.get_text()
        return tag_body


@dataclass
class Reactor(ImageboardParser):
    # this one and class below fails to get soup
    # i dont know, why
    filter_list = ['anime', 'artist', 'фэндомы', 'Игры', '@dcm9«rousbrïde', 'art девушка', 'art (арт)',
                   'Визуальные новеллы', 'Foreign VN (Зарубежные VN)', 'Art vn (vn art)', 'Игровой арт (game art)',
                   'Игровая эротика',
                   'арт барышня (арт девушка, art барышня, art девушка,)', 'naruto porn', 'Witcher Персонажи']

    async def async_get_soup(self, session: any) -> BeautifulSoup:
        responce = await session.get(self.url, params={'proxy': 'None'})
        return bs(responce.text, features='lxml')

    def extract_soup_to_attrs(self, soup: BeautifulSoup | bs.NavigableString) -> None:
        self.tags = soup.find(attrs={'class': "post_description"}, text=True)

    def description_cleaner(self, string) -> None:
        if string is not None:
            string = string.text
            round2 = string.rsplit(' :: ', maxsplit=-1)
            self.tags = list(filter(lambda x: x not in self.filter_list, round2))
        else:
            pass


class Thatpervert(Reactor):
    def __init__(self, url, artist, tags):
        super(Thatpervert, self).__init__(url, artist, tags)


class ParsersHandler:  # in sauce_nao_operations almost same dict used to store links
    # there imageboard names are lowercase to check their precense in urls
    class_dict = {
        'yande.re': Yandere,
        'pixiv': Pixiv,
        'gelbooru': Gelbooru,
        'danbooru': Danbooru,
        'thatpervert': Thatpervert,
        'reactor': Reactor,
        'rule34': Rule34,
        'chan.sankaku': Sankaku,
        'xbooru': Xbooru,
        'anime-pictures': AnimePictures,
    }

    def generate_parsers(self, urls: dict) -> list:  #
        """initializase parsers according to  parsed links from sauce nao"""
        return [self.class_dict[x](urls[x]) for x in self.class_dict if urls[x] is not None]

    @staticmethod
    async def async_call_to_imageboards(parsers: list) -> tuple:
        """Gets soups for allactual parsers asynchronously"""
        proxyes = {
            'https://': venv['PROXY'],
            'http://': venv['PROXY']
        }

        async with httpx.AsyncClient(proxies=proxyes, follow_redirects=True) as sess:
            soups = await asyncio.gather(*[x.async_get_soup(sess) for x in parsers])
        return soups

    @staticmethod
    def extract_soups(soups: typing.Iterable, parsers: list) -> None:
        """Stores html fragments to attrs of actual parsers"""
        for soup in soups:
            parsers[soups.index(soup)].extract_soup_to_attrs(soup)

    @staticmethod
    def clean_all_parsed_tags(parsers: list) -> None:
        """Turns raw text from links into tags for all actual parsers"""
        for parser in parsers:
            parser.remove_all_unnesessary_parsed_info()

    @staticmethod
    def compress_for_reduce(parsers: list, overall_output: dict) -> dict:
        """Stores tags from all actual sites to unified form of dict"""
        for parser in parsers:
            for attr_name in [x for x in parser.parsing_attrs_names if dataclasses.asdict(parser)[x] is not None]:
                overall_output[attr_name].append(dataclasses.asdict(parser)[attr_name])
        return overall_output


async def parse_imageboards(urls: dict) -> dict:
    """Performs full parsing cycle from links from Sauce NAO to tags"""
    common_dict_sample = {
        'fandom': [],
        'character': [],
        'artist': [],
        'tags': []
    }
    handler = ParsersHandler()
    parsers = handler.generate_parsers(urls)
    responces = await handler.async_call_to_imageboards(parsers)
    handler.extract_soups(responces, parsers)
    handler.clean_all_parsed_tags(parsers)
    results = handler.compress_for_reduce(parsers, common_dict_sample)
    return results
