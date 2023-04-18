from __future__ import annotations

import copy
from typing import Iterable, Optional

import requests

from core import exceptions
from parsers.sause_nao_operations import SauseNaoParser, NAOArtistParser, links_to_imageboards
from parsers.validator import ValidatorBuilder
from parsers.yandex_parser import YandexParser


# whole cycle of requesting sources for picture

def get_artists(table: list, main_parser: SauseNaoParser, similarity_degree: str) -> Iterable[Optional[str]]:
    """Gets artist's nicknames from Sauce NAO page through NAOArtistParser"""
    artist_parser = NAOArtistParser(main_parser, [])
    if similarity_degree == 'high':
        return artist_parser.get_artists(
            [x for x in table if float(main_parser.get_similarity_procent(x)) >= 87])
    elif similarity_degree == 'low':
        return artist_parser.get_artists(
            [x for x in table if float(main_parser.get_similarity_procent(x)) <= 87])


def search_for_sources(file, subparser: YandexParser) -> tuple[dict, Iterable[Optional[str]]]:
    # yandex parser creates
    # instance of selenium browser
    # generate new browser every time will slow down reqests miserbly
    # instead code take subparser as argument and re-use browser instance
    with requests.Session() as session:
        main_parser = SauseNaoParser(file, session, copy.copy(links_to_imageboards))
        subparser.parser = main_parser  # yandex parser use part of functional of sauce nao parser
        # and shares the same output dictionary
        watcher = ValidatorBuilder()
        watcher.soup = main_parser.get_soup()
        subparser.url = main_parser.get_redirection_link(watcher.soup)
        # sauce nao allows to search requested picture with another engines
        # if script fails connects to nao and get soup from it
        # search will fail completely
        # becouse redirect link stored in souce nao responce
        watcher.table = main_parser.get_table(watcher.soup)
        watcher.links_to_high_similar_pic = main_parser.get_high_similar_results(watcher.table)
        if watcher.links_to_high_similar_pic:
            main_parser.parse_links_to_imageboards(watcher.links_to_high_similar_pic, main_parser.parsed_links)
            artists = get_artists(watcher.table, main_parser, 'high')
        else:
            watcher.links_to_less_similar_pic = main_parser.get_less_similar_results(watcher.table)
            main_parser.parse_links_to_imageboards(watcher.links_to_less_similar_pic, main_parser.parsed_links)
            artists = get_artists(watcher.table, main_parser, 'low')

        if not any([x for x in main_parser.parsed_links.values() if x != []]):
            raise exceptions.NoSimilarPics

        return main_parser.parsed_links, artists


def search_with_local_file(filepath: str, subparser: YandexParser) -> tuple[dict, Iterable[Optional[str]]]:
    with open(filepath, 'rb') as file:
        return search_for_sources(file, subparser)

