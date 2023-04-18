from __future__ import annotations

import json
from typing import Optional, Mapping, Any

import imagehash as ihsh
import numpy as np
from PIL import Image
from pymongo import MongoClient
from pymongo.database import Database

client = MongoClient('localhost', 27017)
db = client['BrokenNest']


class ImageOpener:
    """
    Class which helps open local stored samples of images.
    Can modify path to sample, if special argument passed.
    """
    def __init__(self, base_dir: str | None, split_image_name: Optional = False):
        self.base_dir: str = base_dir
        self.split_image_name: bool = split_image_name

    @staticmethod
    def split_name(image: str) -> str:
        """Inserts "_thumb' str into path to lacal file"""
        return image.split('.')[0] + '_thumb.' + image.split('.')[1]

    def open(self, image: str) -> Image:
        """Opens local saved sample as PIL Image object"""
        path = f"{self.base_dir}/{image}"
        if self.split_image_name:
            image_ = self.split_name(image)
            path = f"{self.base_dir}/{image_}"
        elif self.base_dir is None:
            path = image
        return Image.open(path)


class IsPictureAlreadyPosted:
    """class to manage samples of stored pictures and compare their hash with new samples"""
    def __init__(self, dir_path: str | Database[Mapping[str, Any] | Any], opener: ImageOpener):
        self._dir_path = dir_path
        self.opener = opener

    @staticmethod
    def id_return(photo_name: str | dict, datafile: dict) -> str | bool:
        """returns id of the post in channel, corresponding to sample, stored locally"""
        if datafile is not db:
            for saved_message in datafile['messages']:
                if 'photo' in saved_message and saved_message['photo'] == photo_name:
                    return saved_message['id']
        elif datafile is db:
            return photo_name['id']
        return False

    @staticmethod
    def set_photo_url(photo: dict, data: dict):
        """Static method to manage paths to local files"""
        if data is db:
            photo_url = photo['src']
        else:
            photo_url = photo
        return photo_url

    def hash_compare(self, image: bytes | Image, similars: list, data: json) -> bool | str:
        """If hash stored sample and new pic are identical, returns id of stored sample, otherwise returns False"""
        if similars:
            model = ihsh.average_hash(image, hash_size=20)
            image_cache = {}
            for photo in similars:
                photo_url = self.set_photo_url(photo, data)
                if photo_url not in image_cache:
                    photo_data = self.opener.open(photo_url)
                    image_cache[photo_url] = ihsh.average_hash(photo_data, hash_size=20)
                sample = image_cache[photo_url]
                if np.count_nonzero(model != sample) <= 0:
                    return self.id_return(photo, data)
            return False
        return False

    @staticmethod
    def find_images_of_same_size(data: json, img_width: str, img_height: str) -> list:
        """Returns a list of images with the specified size present in the database"""
        if data is db:
            return db.posts.find({'width': img_width, 'height': img_height})
        else:
            return [x['photo'] for x in
                    [y for y in data['messages'] if y.get('width') is not None and y.get('photo') is not None] if
                    x['width'] == img_width and x['height'] == img_height]

    def compare_image(self, image: bytes | str, saved_data: json) -> bool | str:
        """Performs search of similar images within specifed json file (chat log from telegramm)"""
        sample_image_model = Image.open(image)
        width, height = sample_image_model.size
        imgs_with_same_size = self.find_images_of_same_size(saved_data, width, height)
        return self.hash_compare(sample_image_model, imgs_with_same_size, saved_data)

    def db_check(self, image: bytes | str) -> bool | str:
        """This function provides ability to swich search of similar images between locally stored jsons and
        database with ip-adress.
        """
        if type(self._dir_path) is str:
            with open(f'{self._dir_path}/result.json', encoding='utf-8') as file:
                saved_data = json.load(file)
                compairing_result = self.compare_image(image, saved_data)
        else:
            saved_data = self._dir_path
            compairing_result = self.compare_image(image, saved_data)

        return compairing_result


def common_result(results: list) -> bool | str:
    """switch-function to turn id of picture into link to corresponding channels"""
    if not any(results):
        return False
    found = [i for i, val in enumerate(results) if val][0]
    match found:
        case 0:
            return f'/brkennest/{results[0]}'
        case 1:
            return f'/c/1435716086/{results[1]}'
        case 2:
            return results[2]
        case _:
            return False


def is_pic_already_posted_check(image: bytes | str) -> bool | str:
    """performs search for similar pictures like specifed pic in all types of databases"""
    comparser_for_broken_nest_db = IsPictureAlreadyPosted(
        'C:/Users/sabla/Downloads/Telegram Desktop/ChatExport_2021-07-09',
        ImageOpener('C:/Users/sabla/Downloads/Telegram Desktop/ChatExport_2021-07-09'))
    comparser_for_anal_carnaval_db = IsPictureAlreadyPosted(
        'C:/Users/sabla/Downloads/Telegram Desktop/ChatExport_2021-07-31',
        ImageOpener('C:/Users/sabla/Downloads/Telegram Desktop/ChatExport_2021-07-31', True))
    comparser_for_bot = IsPictureAlreadyPosted(db, opener=ImageOpener(None))
    comparsers = [comparser_for_broken_nest_db, comparser_for_anal_carnaval_db, comparser_for_bot]
    results = [x.db_check(image) for x in comparsers]
    return common_result(results)
