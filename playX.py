__author__ = "Ernesto"
__email__ = "ernestondieki12@gmail.com"

from configparser import ConfigParser
from os.path import basename, join
from hashlib import shake_256
from threading import Thread


class Counta():

    # Streamline memory usage
    __slots__ = "sectionName", "_logfile", "_CONFIG", "_loaded"

    def __init__(self, workingdir, dst=".", clean: list = None):
        """Manage frequency"""

        self.sectionName = self.shorten_str(basename(workingdir))
        self._logfile = join(dst, "log.cfg")
        self._CONFIG = ConfigParser()
        self._CONFIG.optionxform = str
        # flag variable; 1 if _CONFIG has read a file
        self._loaded = 0
        self._read()
        if clean is not None:
            Thread(target=self.cleanUp, args=(clean, ), daemon=True)
        # self._rename_section(basename(workingdir.replace("[", "").replace("]", "")), self.sectionName)

    def get_freq(self, filename: str = None) -> int:
        """return int: access frequency"""

        if not self._loaded:
            self._read()
        try:
            return int(self._CONFIG[self.sectionName][self.shorten_str(filename)])
        # if filename is not in register
        except KeyError:
            return 0

    def log_item(self, item: str, value: int):
        """shorten item log it with value"""

        if not self._loaded:
            self._read()
        if not self._CONFIG.has_section(self.sectionName):
            self._CONFIG.add_section(self.sectionName)
        self._CONFIG.set(self.sectionName,
                         self.shorten_str(item),
                         str(value))
        self._write()

    def cleanUp(self, items: list):
        # if key does not exist as a valid path, remove option
        if self._CONFIG.has_section(self.sectionName):
            change = 0
            for key in self._CONFIG.options(self.sectionName):
                for filename in items:
                    if self.shorten_str(filename) == key:
                        break
                else:
                    self._CONFIG.remove_option(self.sectionName, key)
                    # flag change happened
                    change = 1
                continue
            # write changes; else pass
            if change:
                self._write(clear=0)

    @staticmethod
    def shorten_str(string) -> str:

        return shake_256(string.encode("utf-8")).hexdigest(8)

    def _read(self):
        callback = self._CONFIG.read(self._logfile, encoding="utf-8")
        # _CONFIG is loaded
        if callback:
            self._loaded = 1

    def _write(self, clear=1):
        with open(self._logfile, "w", encoding="utf-8") as f:
            self._CONFIG.write(f)
        if clear:
            self._CONFIG.clear()
            # _CONFIG is not loaded
            self._loaded = 0

    def _rename_section(self, sect: str, new_sect: str):
        if self._CONFIG.has_section(sect):
            items = self._CONFIG.items(sect)
            self._CONFIG.add_section(new_sect)
            for item in items:
                key = self.shorten_str(item[0])
                self._CONFIG.set(new_sect, key, item[1])
            self._CONFIG.remove_section(sect)
