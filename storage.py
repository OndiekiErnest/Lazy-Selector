""" json-settings manager and cache tools """

import re
import os
import orjson
import shutil
from typing import (
    Any,
    Optional,
)
from diskcache import (
    FanoutCache,
    Cache,
)
from core import (
    BASE_DIR,
)


OPTS_KEYS = {"theme", "window", "folders", "searches"}
DEFAULT_SETTINGS = {
    "theme": {
        "bg": "gray28",
        "fg": "gray97"
    },
    "window": {
        "donotshow": "0",
        "position": "5+5"
    },
    "folders": {
        "last": ""
    },
    "searches": {
        "last": "official music video",
        "all": []
    }
}


WIN_PATT = re.compile(r"[0-9]{1,4}\+[0-9]{1,4}")


def win_pos(pos) -> Optional[re.Match]:
    return WIN_PATT.search(pos)


def _validate_win(parent: str, key: str, value: str):
    """ return valid window value """
    if key == "position":  # special handling of position
        found = win_pos(value)
        if found:  # return; else return default
            return found.string  # return found.str cos it matches regex
    else:
        valid_opts = {
            "donotshow": {"1", "0"},
        }
        opt = valid_opts.get(key)
        if opt:  # if it's validated
            if value in opt:  # check membership
                return value  # return; else return default
        else:  # if it's not validated
            return value

    return DEFAULT_SETTINGS[parent][key]


def _validate_theme(parent: str, key: str, value: str):
    """ return valid theme value """
    valid_themes = {
        "bg": {"gray28", "gray97"},
        "fg": {"black", "gray97"}
    }
    theme = valid_themes.get(key)
    if theme:  # if it's validated
        if value in theme:
            return value  # return; else return default
    else:  # if it's not validated
        return value

    return DEFAULT_SETTINGS[parent][key]


def get_actime(filename: str):
    """ get access and created time of file """
    stat = os.stat(filename)
    return stat.st_atime, stat.st_ctime


VALIDATORS = {
    "theme": {
        "bg": _validate_theme,
        "fg": _validate_theme
    },
    "window": {
        "donotshow": _validate_win,
        "position": _validate_win
    },
    "folders": {
        "last": None
    },
    "searches": {
        "last": None,
        "all": None
    }
}


class AppConfigs():
    """ class to read/write settings to/from json """

    def __init__(self, config_file: str):
        self.filename = config_file
        # read data; get data
        self._read(config_file)

    def _validate(self, data: dict):
        """ make sure the values are valid """
        data = {k: v for k, v in data.items() if (k in OPTS_KEYS)}  # clean data
        data_values = data.values()

        for key, values, funcs in zip(OPTS_KEYS, data_values, VALIDATORS.values()):
            for value, v_func in zip(values.items(), funcs.items()):
                _, inner_v = value  # discard v_key here cos it can be changed by user
                v_key, func = v_func  # use v_key from VALIDATORS

                if func:
                    valid_v = func(key, v_key, inner_v)
                    data[key][v_key] = valid_v
        return data

    def _read(self, filename: str):
        """ read from json """

        try:
            with open(filename, "rb") as file:
                data = orjson.loads(file.read())
                if data:
                    self.data = self._validate(data)
                else:
                    self.data = DEFAULT_SETTINGS
        except Exception:  # KeyError
            self.data = DEFAULT_SETTINGS

    def _write(self, data: dict):
        """ write data to json """

        with open(self.filename, "wb") as file:
            serialized = orjson.dumps(
                data,
                option=orjson.OPT_INDENT_2
            )
            file.write(serialized)

    def save(self):
        """ save available data to file """
        self._write(self.data)

    def get(self, key: str) -> Optional[Any]:
        """ get, return value of key """
        return self.data[key]

    def get_inner(self, parent: str, key: str) -> Optional[Any]:
        """ get value of key from parent """
        return self.data[parent][key]

    def update(self, key: str, value: Any):
        """ update key with value """
        if self.data:
            self.data.update({key: value})
        else:
            self.data = {key: value}

    def update_inner(self, parent: str, key: str, value: Any):
        """ update value of key from parent """
        if self.data:
            inner = self.data.get(parent)
            if inner:
                self.data[parent].update({key: value})
            else:
                self.data[parent] = {key: value}
        else:
            self.data = {parent: {key: value}}


class DCache():
    """
    cache to file using diskcache
    disk usage is upto 1GB,
    the dir is deleted on closing the app
    """

    def __init__(self, cache_dir: str):
        self.cache_data = FanoutCache(
            directory=cache_dir,
            timeout=1,
        )
        # create keys
        self.cache_data["streams"] = {}
        self.cache_data["metadata"] = {}

    def get_stream(self, url: str):
        """ return cached value of sinfo dict or None """
        return self.cache_data["streams"].get(url)

    def get_metadata(self, name: str):
        """ get metadata dict or None used in Properties """
        return self.cache_data["metadata"].get(name)

    def cache_stream(self, url: str, sinfo):
        """ cache sinfo dict """
        streams = self.cache_data["streams"]
        streams.update({url: sinfo})

        self.cache_data["streams"] = streams

    def cache_metadata(self, name: str, metadata: dict):
        """ cache local file metadata used in Properties """
        data = self.cache_data["metadata"]
        data.update({name: metadata})

        self.cache_data["metadata"] = data

    def clear_cache(self):
        """ clear all data """
        self.cache_data.clear()
        # create keys
        self.cache_data["streams"] = {}
        self.cache_data["metadata"] = {}

    def close_cache(self):
        """ close and delete cache dir """
        try:
            self.cache_data.close()
            shutil.rmtree(self.cache_data.directory)
        except Exception:
            pass


class TrackRecords():
    """
    stores:
    play counter
    uses diskcache for its speed
    """

    def __init__(self, track_records_dir: str, folder_path: str):
        self.track_records_dir = track_records_dir  # used for keeping records
        self.folder_path = folder_path  # used for cleaning and getting folder name

        # if folders in defferent paths share the same name
        # eliminate the likelihood of cleaning contents of the other
        paths = [name for name in re.split(f"[\\\\:/]", folder_path) if name]  # remove empty str
        if len(paths) > 1:
            folder_name = f"{'_'.join(paths[-2].split())}_{''.join(paths[-1].split())}"
        else:
            folder_name = '_'.join(f"{''.join(paths)} disk".split())

        cwd = os.path.join(track_records_dir, folder_name)  # current working dir for track records

        self.records = Cache(
            directory=cwd,
        )
        # clean
        self._clean()
        # try to remove old support
        old_records = os.path.join(BASE_DIR, "data", "log.cfg")
        if os.path.exists(old_records):
            os.remove(old_records)

    def sortbykey(self, name: str) -> tuple:
        """
        get frequency of filename
        return:
        last access time,
        created time,
        negative play count
        (in that order)
        """
        filename = os.path.join(self.folder_path, name)
        a_time, c_time = get_actime(filename)  # get a_time, c_time from file
        counter = self.records.get(name, default=0)

        return (a_time, c_time, -counter)

    def _freq(self, name: str) -> int:
        """ get the play count, specifically """

        counter = self.records.get(name, default=0)
        if counter:
            return int(counter)
        return 0

    def log(self, filename: str):
        """
        create new entry for filename
        """
        name = os.path.basename(filename)
        counter = self._freq(name) + 1

        self.records[name] = counter  # just log counter

    def _clean(self):
        """ remove tracks-not-found records """
        folder = self.folder_path
        keys = self.records.iterkeys()
        with self.records.transact():
            for k in keys:
                file = os.path.join(folder, k)
                if not os.path.isfile(file):
                    self.records.delete(k)

    def close(self):
        """ close track records """
        self.records.close()
