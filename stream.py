__author__ = "Ernesto"
__email__ = "ernestondieki12@gmail.com"


from youtubesearchpython import VideosSearch
import ctypes
from locale import windows_locale
from typing import Optional

RESULTS_LIMIT = 30
LANG = windows_locale[ctypes.windll.kernel32.GetUserDefaultUILanguage()]


class Stream():
    __slots__ = ("done", )

    def __init__(self):
        self.done = 0

    def search(self, query_str) -> Optional[dict]:
        """ get video metadata; return a simpler dict, {title: link}"""

        self.done = 0
        title_link = {}
        try:
            response = VideosSearch(query_str, language=LANG, limit=RESULTS_LIMIT)
            for i in range(3):  # get 3 pages of the results
                results = response.result()
                for item in results.get("result", {}):
                    title, link = item.get("title"), item.get("link")
                    if title and link:
                        title_link.setdefault(title, link)
                response.next()
            self.done = 1
            return title_link

        except Exception:
            self.done = 1
            return


if __name__ == "__main__":
    title_link = Stream().search("deep house mix")
    print(title_link)
