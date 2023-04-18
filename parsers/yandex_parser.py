import typing

import bs4
import undetected_chromedriver as uc
from bs4 import BeautifulSoup as bs
from selenium.webdriver.support.expected_conditions import presence_of_all_elements_located
from selenium.webdriver.support.wait import WebDriverWait

from parsers.sause_nao_operations import SauseNaoParser


# Yandex sometimes returns results, which SauseNao didnt find (regarding links to Gelbooru, etc).
# In addition Yandex have unique results, like links to .reactor sites, which could be parsed too.
# Problem is most of search results loads to page via ajax, which can be parsed (probably only) with selenium.
# Since reverse search has various gaps between requests, for avoidance of bans and etc, Undetected Chromedriver (UC) used
# However, UC is very capricious library, beware of using it

class UndetectedSelenium:
    """
    Basic class interhited from selenium, to hide initialization of Chromium with nesessary options
    """

    def __init__(self, main_version: int, browser: uc = None):
        self.version: int = main_version
        self.browser: uc = browser

    def create_browser(self) -> None:
        """
        Initialisizes maximally simplified selenium browser object
        :return: On succes, headless Chromium object created in self.browser
        """
        options = uc.ChromeOptions()
        options.add_argument('--blink-settings=imagesEnabled=false')
        options.add_argument('--no-sandbox')
        options.add_argument('--no-first-run')
        options.add_argument('--block-new-web-contents')
        options.add_argument('--headless=new')
        self.browser = uc.Chrome(options=options, version_main=self.version)


class YandexParser(UndetectedSelenium):
    """Specialised class for parsing yandex image search page"""
    blacklist: typing.ClassVar[tuple[str]] = ('thumbnail', 'search', 'news', 'popular', 'sexiezpic',
                                              'hentai-img', 'hentaiporns', 'img10', 'vk.com')
    endswith_blacklist: typing.ClassVar[tuple[str]] = ('.png', '.jpg', '.jpeg')

    def __init__(self, version: typing.Optional[int],  parser: SauseNaoParser = None,
                 url: typing.Optional[str] = None):
        super().__init__(main_version=version)
        self.is_on = 0
        self.parser = parser
        self.url = url

    def get_url(self, url: str) -> None:
        """wrapper around browser window open process, provides ability to count
        and manage open windows, which is removed from Undetected Selenium"""
        self.is_on += 1
        if self.is_on >= 2:
            self.browser.close()
        return self.browser.get(url)

    def get_yandex_soup(self, yandex_url: str) -> list[bs4.PageElement]:
        """
        Gets list of links in part of search page below image sample and other sizes of it.

        :param yandex_url: redirection link to yandex, got from SauseNao
        :return: list[bs4.PageElement]
        """
        self.browser.get(yandex_url)
        WebDriverWait(self.browser, 10).until(presence_of_all_elements_located)
        yandex_page = self.browser.page_source
        soup = bs(yandex_page, features='lxml')
        yandex_cells = [x.extract() for x in soup.find_all(class_='CbirSites-Item')]
        return yandex_cells

    @staticmethod
    def get_yandex_link_with_description(html_block: bs4.NavigableString) -> tuple[str, str]:
        """Packs titles and links of parsed page elements into tuples
         -> tuple[title, url]"""
        descripton = html_block.div.nextSibling.text
        link = html_block.div.a.get('href')
        return descripton, link

    def yandex_filter(self, info_tuple) -> bool:
        """Returns False If any unwanted part is present in url or title"""
        if not [x for x in self.parser.parsed_links if x in str(info_tuple[1])] or \
                [x for x in self.blacklist if x in str(info_tuple[1])] or \
                [x for x in self.endswith_blacklist if str(info_tuple[1]).endswith(x)]:
            return False
        else:
            return True

    def full_parcing_cycle(self, browser: uc = None) -> None:
        """Gets and filters links from yandex reverse search page, using
        parsers.sause_nao_operations SauseNaoParser's parse_links_to_imageboards method"""
        if browser:
            self.browser = browser
        soup = self.get_yandex_soup(self.url)
        links = map(self.get_yandex_link_with_description, soup)
        filtered_links = tuple(filter(self.yandex_filter, links))
        self.parser.parse_links_to_imageboards(filtered_links, self.parser.parsed_links)
