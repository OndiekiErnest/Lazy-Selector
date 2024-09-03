""" search youtube """

import logging
import ctypes
from locale import windows_locale
from typing import Optional
from youtubesearchpython import VideosSearch

RESULTS_LIMIT = 30
LANG = windows_locale[ctypes.windll.kernel32.GetUserDefaultUILanguage()]


logger = logging.getLogger(__name__)

class YTSearch():
    __slots__ = ("done", )

    def __init__(self):
        self.done = 0

    def search(self, query_str) -> Optional[dict]:
        """ get video metadata; return a simpler dict, {title: link}"""

        self.done = 0
        title_link = {}
        try:
            response = VideosSearch(query_str, language=LANG, limit=RESULTS_LIMIT)
            for _ in range(3):  # get 3 pages of the results
                results = response.result()
                for item in results.get("result", {}):
                    title, link = item.get("title"), item.get("link")
                    if title and link:
                        title_link[title] = link
                response.next()
            self.done = 1
            return title_link

        except Exception as e:
            logger.exception(e)
            self.done = 1
            return
