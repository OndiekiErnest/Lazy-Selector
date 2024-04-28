""" Lazy Selector app """

__VERSION__ = "5.0.0"
# Run all_songs shuffle and sort in background

# from profiler import profile_function
import vlcmixer as mixer
from streams.search import YTSearch
from streams.YT import (
    get_sanitizedinfo,
    get_video_streams,
    get_audio_streams,
    get_url_details,
    get_play_stream,
)
from streams.downloader import (
    ADownloader,
    Task,
)
from streams.utils import (
    prevent_sleep,
    allow_sleep,
    file_details,
    safe_delete,
    strfdelta,
    is_url,
    r_path,
)
from core import (
    EXTS,
    BASE_DIR,
    scroll_widget,
)
from concurrent.futures import ThreadPoolExecutor
from socket import gethostname, gethostbyname
from multiprocessing import (
    Manager, freeze_support
)
from multiprocessing.managers import (
    SyncManager,
)
from stat import S_IREAD, S_IWUSR
from plyer import battery, notification
import sys
import os
import orjson
from send2trash import send2trash
# from random import shuffle
import images
from time import sleep, time
from datetime import timedelta
from tkinter import (
    Tk, Frame, Label,
    Button,
    PhotoImage,
    Menu, DoubleVar,
    Listbox, Entry,
    Scrollbar, Toplevel,
    Canvas,
    BooleanVar
)

from tkinter.ttk import Scale, Notebook, Style
from ttkthemes import ThemedStyle
try:
    from idlelib.tooltip import ToolTip
# for python greater than 3.7
except ImportError:
    from idlelib.tooltip import Hovertip as ToolTip
from dialogs import (
    DetailsPopup,
    showinfo, okcancel,
    getquality,
)
from tkinter.filedialog import (
    askopenfilenames, askdirectory
)
from storage import (
    AppConfigs, DCache,
    TrackRecords,
)
from ctypes import windll
from webbrowser import open as open_tab


DATA_DIR = r_path("data", base_dir=BASE_DIR)
TRACK_RDIR = os.path.join(DATA_DIR, "trackrecords")  # track records dir
CACHE_DIR = os.path.join(DATA_DIR, "appcache")
QUEUE_FILE = os.path.join(CACHE_DIR, "queue.json")

EXIFTOOL_PATH = os.path.join(r_path("exiftool", base_dir=BASE_DIR), "exiftool.exe")
CURRENT_PID = os.getpid()


def handle_yt_errors(error) -> str:
    """ return a friendly string for error """
    return "An error has occured while fetching info..."


def get_q(filename) -> list:
    """ get files written to this file """
    with open(filename, "rb") as q_file:
        data = orjson.loads(q_file.read())
        if data:
            set_q(QUEUE_FILE, [])
        return data


def set_q(filename, data: list):
    """ write data to json """

    with open(filename, "wb") as q_file:
        serialized = orjson.dumps(
            data,
            option=orjson.OPT_INDENT_2
        )
        q_file.write(serialized)


class Options():
    __slots__ = ()
    # in seconds
    TIMEOUT = 20
    LISTBOX_OPTIONS = {"bg": "white smoke", "fg": "black", "width": 42,
                       "selectbackground": "DeepSkyBlue3", "selectforeground": "white",
                       "height": 43, "relief": "flat",
                       "font": ("New Times Roman", 9), "highlightthickness": 0}

    SCALE_OPTIONS = {"from_": 0, "orient": "horizontal", "length": 225, "cursor": "hand2"}
    FILENAMES_INITIALDIR = os.path.expanduser("~\\Music")
    ALT_DIRS = {FILENAMES_INITIALDIR, }


class Player(Options):
    """
        Plays audio and video files in
        win is tkinter's toplevel widget Tk
    """
    _CONFIG = AppConfigs(os.path.join(DATA_DIR, "lazylog.cfg"))

    BG = _CONFIG.get_inner("theme", "bg")
    FG = _CONFIG.get_inner("theme", "fg")

    # @profile_function
    def __init__(self, win, shared_dict: SyncManager.dict):
        self._root = win
        self.shared_dict = shared_dict
        self._root.resizable(0, 0)
        self._root.config(bg=Player.BG)
        self._root.title("Lazy Selector")
        self._root.tk_focusFollowsMouse()
        self._root.wm_protocol("WM_DELETE_WINDOW", self._kill)
        self.uptime_loopid = self._root.after(1000, self._set_uptime)
        # use png image for icon
        self._root.wm_iconphoto(1, PhotoImage(data=images.APP_IMG))
        # for screens with high DPI minus 102
        self._screen_height = self._root.winfo_screenheight() - 104 if self._root.winfo_screenheight() >= 900 else self._root.winfo_screenheight() - 84

        self.shuffle_mixer = mixer.VLC()
        self.video_search = YTSearch()
        self._progress_variable = DoubleVar()
        self.mute_variable = BooleanVar()
        self.loopone_variable = BooleanVar()

        # get last window position
        position = Player._CONFIG.get_inner("window", "position")
        # get last search
        self.search_str = Player._CONFIG.get_inner("searches", "last")
        # get search history
        self._search_history = set(Player._CONFIG.get_inner("searches", "all"))

        self._root.geometry("318x118+" + position)

        self.progressbar_style = ThemedStyle()
        self.progressbar_style.theme_use("equilux")
        self.progressbar_style.configure("custom.Horizontal.TScale", background=Player.BG)
        self.progressbar_style.configure("TButton", foreground="gray97", focuscolor="gray97")
        self.progressbar_style.configure("TCombobox", foreground="gray97")

        self.threadpool = ThreadPoolExecutor(max_workers=5)
        # create cache
        self.file_cache = DCache(CACHE_DIR)
        self._all_files = []
        self.collected = []
        self.index = -1
        self.collection_index = -1
        self.stream_index = -1
        self._uptime = 0
        self.tab_num = 0
        self.isStreaming = 0
        self.change_stream = 1
        self._title_link = None
        # let duration be greater than 0; prevent slider being at the end on startup
        self.duration = 60
        self._song = ""
        self._title_txt = ""
        self.ftime = "00:00"
        self._play_btn_command = None
        self._play_prev_command = None
        self._play_next_command = None
        self.list_frame = None
        self.listbox = None
        self.controls_frame = None
        self.main_frame = None
        self.done_frame = None
        self.top = None
        self._slider_above = 0
        self._playing = 0
        self.lowbatt_notified = 0
        self.reset_preferences = 0

        self._supported_extensions = tuple(EXTS)
        # value to let refresher open dir chooser; otherwise use previous
        self._open_folder = 0
        self.previous_img = PhotoImage(data=images.PREVIOUS_IMG)
        self.play_img = PhotoImage(data=images.PLAY_IMG)
        self.pause_img = PhotoImage(data=images.PAUSE_IMG)
        self.next_img = PhotoImage(data=images.NEXT_IMG)
        self.lpo_image = PhotoImage(data=images.LDARKPOINTER_IMG)
        self.play_btn_img = self.play_img

        if Player.BG == "gray97":
            self.more_image = PhotoImage(data=images.MORE_IMG)
            self.rpo_image = PhotoImage(data=images.POINTER_IMG)
        else:
            self.more_image = PhotoImage(data=images.DARKMORE_IMG)
            self.rpo_image = PhotoImage(data=images.DARKPOINTER_IMG)

        self.menubar = Menu(self._root)
        self._root.config(menu=self.menubar)
        self.file_menu = Menu(self.menubar, tearoff=0,
                              fg=Player.FG, bg=Player.BG)
        self.menubar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Open Folder",
                                   command=self._manual_add)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Add to Queue",
                                   command=self._select_fav)

        self.theme_menu = Menu(self.menubar, tearoff=0,
                               fg=Player.FG, bg=Player.BG)
        self.menubar.add_cascade(label="Theme", menu=self.theme_menu)
        self.theme_menu.add_command(label="Light",
                                    command=lambda: self._update_color("gray97", "black"))
        self.theme_menu.add_separator()
        self.theme_menu.add_command(label="Dark",
                                    command=lambda: self._update_color("gray28", "gray97"))

        self.about_menu = Menu(self.menubar, tearoff=0, selectcolor=Player.FG,
                               fg=Player.FG, bg=Player.BG)
        self.menubar.add_cascade(label="Help", menu=self.about_menu)
        self.about_menu.add_command(label="Switch Slider", command=self._change_place)
        self.about_menu.add_separator()
        self.about_menu.add_checkbutton(label="Reset preferences", command=self._remove_pref)
        self.about_menu.add_separator()
        self.about_menu.add_command(label="About Lazy Selector", command=self._about)

        file_passed = self._refresher()
        self._init()
        if file_passed:
            self.on_eos()

        rem_battery = battery.get_state()["percentage"]
        if (rem_battery < 41) and (rem_battery > 16):
            notification.notify(
                title="Lazy Selector",
                message=f'{rem_battery}% Charge Available',
                app_name="Lazy Selector",
                app_icon=f"{DATA_DIR}\\app.ico" if os.path.exists(f"{DATA_DIR}\\app.ico") else None
            )

    # ------------------------------------------------------------------------------------------------------------------------------

    def send_event(
        self, funcname: str,
        *args,
        **kwargs
    ):
        """
        put funcname, args, and kwargs as a `Task` in shared_dict
        for the downloader to pick
        """

        msg = Task(funcname, args, kwargs)
        self.shared_dict["task"] = msg
        while True:
            rtv = self.shared_dict.pop(funcname, "00")
            if rtv != "00":
                return rtv
            sleep(0.01)

    def update_downloader_progress(self):
        """ get and update downloader progress from downloader """

        progress_txt = self.shared_dict.pop("progress", None)
        if progress_txt:  # not None or empty str
            try:
                self.status_bar.configure(text=progress_txt)
            except Exception:  # when statusbar is destroyed
                pass
        # repeat infinitely until cancelled
        self.progress_loopid = self.status_bar.after(
            700, self.update_downloader_progress
        )

    def cancel_afters(self):
        """ cancel all after calls on close """
        try:
            self.status_bar.after_cancel(self.progress_loopid)
        except AttributeError:
            pass
        self._root.after_cancel(self.uptime_loopid)

    def close_playlistwindow(self):
        """ close playlist window if available """

        self.controls_frame.pack_forget()
        try:
            self.status_bar.after_cancel(self.progress_loopid)
        except Exception:
            pass
        self.list_frame.pack_forget()
        self.listbox.pack_forget()
        self.scrollbar.pack_forget()
        self.controls_frame, self.list_frame = None, None
        self.listbox, self.scrollbar = None, None
        self.progress_bar.style = None
        self.controls_frame = None
        self.collected = []
        self.tab_num = 0

    def toggle_sleep(self):
        """ if player and downloader are idle sleep """
        if (self.is_downloading() and self._playing):
            prevent_sleep()
        else:
            allow_sleep()

    def _on_enter(self, event):
        """
            On mouse over widget
        """

        event.widget["bg"] = "gray97"

    def _on_leave(self, event):
        """
            On mouse leave widget
        """

        if self.controls_frame is not None:
            event.widget["bg"] = "gray28"
        else:
            # use the current theme on leave; that includes light
            event.widget["bg"] = Player.BG

    def _convert(self, text: str):
        """
            Trims title text
        """
        if len(text) > 46:  # not so perfect
            if text[:46].isupper():
                text = f"{text[:43]}..."
            else:
                text = f"{text[:45]}..."
        return text

    @property
    def isOffline(self) -> bool:
        """ return True if no internet """
        return gethostbyname(gethostname()) == "127.0.0.1"

    def get_sinfo(self, url) -> dict:
        """
        get sinfo from either cache or
        extract, cache and return it
        """
        sinfo = self.file_cache.get_stream(url)
        if not sinfo:
            sinfo = get_sanitizedinfo(url)
            if sinfo:
                self.file_cache.cache_stream(url, sinfo)
        return sinfo

    def file_fromlistbox(self, index: int) -> str:
        """
        get selected file of listbox index
        from either all_files or collected
        """
        if self.collected:
            return self.collected[index]
        return self._all_files[index]

    # ------------------------------------------------------------------------------------------------------------------------------

    def _update_bindings(self):
        """
            Mouse hover bindings; to change background of button in dark mode
        """

        if self.controls_frame is not None or Player.BG == "gray28":
            self._previous_btn.bind("<Enter>", self._on_enter)
            self._previous_btn.bind("<Leave>", self._on_leave)
            self._play_btn.bind("<Enter>", self._on_enter)
            self._play_btn.bind("<Leave>", self._on_leave)
            self._next_btn.bind("<Enter>", self._on_enter)
            self._next_btn.bind("<Leave>", self._on_leave)

    # ------------------------------------------------------------------------------------------------------------------------------

    def __update_listbox(self):
        """
            Inserts items to the Listbox
        """

        self.listbox.pack_forget()
        self.scrollbar.pack_forget()
        self.searchlabel.configure(text="Updating...")
        self.searchlabel.place(x=10, y=72)
        self.collection_index = -1
        self.collected = []
        # self.searchbar.delete(0, "end")
        self.listbox.delete(0, "end")
        try:
            self.back_toplaylist_btn.destroy()
        except AttributeError:
            pass
        try:
            # self._root.geometry("318x118+")
            for file in self._all_files:
                self.listbox.insert("end", file)

            self.listbox_select(self.index)
            self.listbox.pack(side="left", padx=3)
            self.scrollbar.pack(side="left", fill="y")
            self._resize_listbox()
        except AttributeError:
            pass

    def _update_listbox(self):
        """
            Threads __update_listbox function
            Inserts items to listbox from self._all_files
        """

        if self.listbox is not None and self.scrollbar is not None:
            self.threadpool.submit(self.__update_listbox)

    # ------------------------------------------------------------------------------------------------------------------------------

    def _resize_listbox(self):
        """
            Dynamically resize Listbox according to the number of items
        """

        self.searchbar.place(x=178, y=73)
        if self.listbox.size() > 35:
            self._root.geometry(f"318x{self._screen_height}+" + f"{self._root.winfo_x()}+{5}")
            if not self.tab_num:
                self.searchlabel.configure(text="Search:")
            else:
                self.searchlabel.configure(text="Search online:")
        elif self.listbox.size() > 0:
            # one line takes 16 pixels on my machine
            height = 124 + (self.listbox.size() * 16)
            y = self._root.winfo_y()
            difference = self._screen_height - (y + height)
            # if the new height surpasses screen bottom, then subtract the difference from y to get new y
            if difference < 0:
                y = y - (difference * -1)
                if y < 5:  # prevent the window from going beyond the screen top
                    y = 5
            self._root.geometry(f"318x{height}+" + f"{self._root.winfo_x()}+{y}")
            if not self.tab_num:
                self.searchlabel.configure(text="Search:")
            else:
                self.searchlabel.configure(text="Search online:")
        else:
            self._root.geometry(f"318x{self._screen_height}+" + f"{self._root.winfo_x()}+{5}")
            self.searchlabel.configure(text="No files found!")
        # direct focus to searchbar
        # self.searchbar.focus_set()

    # ------------------------------------------------------------------------------------------------------------------------------

    def __on_search(self):
        """
            updates listbox with match for string searched else updates listbox
            fetches and updates online streams if tab_num is 1
        """
        self.searchbar.selection_clear()
        search_string = self.searchbar.get()
        if len(search_string) > 1:
            if len(self._search_history) >= 61:  # keep upto 60 searches
                self._search_history.pop()

            if self.tab_num:
                # online
                if not self.isOffline:
                    self.searchlabel.configure(text="Updating...")
                    # do search here bacause;
                    # this function is threaded,
                    # query_str is needed; unlike _handle_stream_tab's search
                    if is_url(search_string):
                        self.searchlabel.configure(text="Extracting url...")

                        sinfo = self.get_sinfo(search_string)

                        title = get_url_details(sinfo, only="title")
                        if title:  # is not None:
                            # update, placed last if not in _title_link
                            self._title_link[title] = search_string
                            # update gui
                            self._handle_stream_tab()  # blocking
                            try:
                                # get index using title after updating gui
                                index = self.listview.get(0, "end").index(title)
                            except ValueError:
                                index = -1
                            self.listview_select(index)
                        else:
                            # no title is found, sinfo is empty
                            self.status_bar.configure(text="Could not extract url...")
                    else:  # else is search str
                        self._search_history.add(search_string)  # save only online searches
                        self.search_str = search_string  # avoid saving link as last search
                        self._title_link = self.video_search.search(search_string)
                        # update listview window in streams tab
                        self.thread_updating_streams()
                        self.stream_index = -1
                    if self.tab_num:
                        self.searchlabel.configure(text="Search online:")
                    else:
                        self.searchlabel.configure(text="Search:")
            else:
                # local files tab
                self.collected = []
                self.collection_index = -1
                try:
                    self.back_toplaylist_btn.destroy()
                except AttributeError:
                    pass
                # ---------------------------------back button-------------
                self.back_toplaylist_btn = Button(self.controls_frame, image=self.lpo_image, bg="gray28",
                                                  pady=0, relief="flat", width=66, height=12)
                self.back_toplaylist_btn.place(x=3, y=74)
                # ToolTip(self.back_toplaylist_btn, "Leave search-results playlist", hover_delay=0)
                search_str = search_string.lower()
                # ---------------------------------
                self.listbox.delete(0, "end")
                self.collected = [song for song in self._all_files if search_str in song.lower()]
                self.listbox.insert("end", *self.collected)
                self._resize_listbox()
                # give the button functionality after update is done
                self.back_toplaylist_btn.configure(command=self._update_listbox)

        else:
            if (not self.tab_num):
                if self.listbox.size() != len(self._all_files):
                    self._update_listbox()

    def _on_search(self, event):
        """
            Threads __on_search function
        """

        self.threadpool.submit(self.__on_search)

    def complete_searches(self, event):
        """ suggest inline """
        if (len(event.keysym) == 1) and (event.char):  # skip special keys

            if self._search_history:
                typed = self.searchbar.get()
                start = len(typed)
                match = ""
                for sw in self._search_history:
                    if sw.startswith(typed):
                        match = sw
                        break

                if match:
                    # update searchbar
                    self.searchbar.delete(0, "end")
                    self.searchbar.insert(0, match)
                    self.searchbar.selection_range(start, "end")

    def entryhighlight(self, event=None):
        """ highlight text whenever search entry takes focus """

        if event is not None:
            event.widget.selection_range(0, "end")

    def _file_metadata(self, file: str, title: str):
        """ get file metadata """
        try:
            # get local file details
            details = self.file_cache.get_metadata(title)
            if not details:
                details = file_details(file, exiftool_path=EXIFTOOL_PATH)
                self.file_cache.cache_metadata(title, details)

            DetailsPopup(self._root, title, details, bg="white")
        except IndexError:
            pass

    def _file_details(self):
        """ get and display file metadata """
        index = self.listbox.curselection()[-1]
        title = self.file_fromlistbox(index)
        filename = self.valid_path(title)
        # thread
        self.threadpool.submit(
            self._file_metadata,
            filename, title
        )

    def _url_metadata(self, url: str, title: str):
        """ popup url details """
        try:
            sinfo = self.get_sinfo(url)

            if sinfo:
                details = get_url_details(sinfo)  # dict for display
                DetailsPopup(self._root, title, details, bg="white")
            else:
                self.status_bar.configure(text="Could not fetch metadata...")
        except Exception:
            pass
        self.status_bar.configure(text="")

    def _url_details(self):
        """ get and display url metadata """
        self.status_bar.configure(text="Fetching metadata...")
        title = self.listview.selection_get()
        url = self._title_link.get(title)
        # get metadata
        self.threadpool.submit(
            self._url_metadata,
            url, title
        )
    # ------------------------------------------------------------------------------------------------------------------------------

    def _on_refresh(self):
        """ refresh playlist files function """
        self.index = -1
        all_files = os.listdir(self._songspath)
        self._all_files = [i for i in all_files if i.endswith(self._supported_extensions)]
        # shuffle(self._all_files)
        with self.track_records.records.transact():  # context manager to lock records
            self._all_files.sort(key=self.track_records.sortbykey)
        if self.listbox is not None:
            self._update_listbox()

    # ------------------------------------------------------------------------------------------------------------------------------

    def _delete_listitem(self):
        """
            Listbox's Remove from Playlist
        """

        for i in reversed(self.listbox.curselection()):
            if not self.collected:
                item = self._all_files[i]
                self._all_files.remove(item)
            else:
                item = self.collected[i]
                self.collected.remove(item)

            self.listbox.delete(i)
            if i <= self.index:
                # adjust to playlist shifting
                self.index -= 1
        self._resize_listbox()

    # ------------------------------------------------------------------------------------------------------------------------------

    def _remove_streams(self):
        """ remove selected streams from view """
        for i in reversed(self.listview.curselection()):
            title = self.listview.get(i)
            self._title_link.pop(title, None)
            self.listview.delete(i)

    # ------------------------------------------------------------------------------------------------------------------------------

    def _send2trash(self):
        """
            Try sending to trash if not removable disk, else delete permanently
        """
        selected = self.listbox.curselection()
        if selected:
            answer = okcancel(self._root,
                              "Lazy Selector",
                              "Selected files will be deleted from storage\nContinue to delete?"
                              )
            if answer:
                for i in reversed(selected):

                    if self.collected:
                        item = self.collected[i]
                        self.collected.remove(item)
                        if i <= self.collection_index:
                            # adjust to 'collected' shifting
                            self.collection_index -= 1
                    else:
                        item = self._all_files[i]
                        self._all_files.remove(item)
                        if i <= self.index:
                            # adjust to playlist shifting
                            self.index -= 1

                    self.listbox.delete(i)
                    # delete file
                    filename = os.path.normpath(self.valid_path(item))
                    try:
                        # go to next before deleting to avoid 'file is open by another program' error
                        if filename == self._song:
                            self._play_prev(prev=0)
                        send2trash(filename)
                    except Exception:
                        safe_delete(filename)

                self._resize_listbox()

    # ------------------------------------------------------------------------------------------------------------------------------

    def _addto_queue(self):
        """
            Listbox's Play Next
        """
        try:
            i = self.listbox.curselection()[-1]

            if (not self.collected) and (i != self.index and i != self.index + 1):  # if adding from main list
                item = self._all_files[i]

                try:
                    if i > self.index:
                        # if the selected item is below the currently, delete first to avoid shift in indexes
                        # deleting after insertion shifts the item down by 1
                        self.listbox.delete(i)
                        self._all_files.remove(self._all_files[i])  # remove item
                        self.listbox.insert(self.index + 1, item)
                        self._all_files.insert(self.index + 1, item)
                    else:
                        # insert first then delete before items shift up, including the currently playing
                        self.listbox.insert(self.index + 1, item)
                        self._all_files.insert(self.index + 1, item)
                        self.listbox.delete(i)
                        self._all_files.remove(self._all_files[i])  # remove item
                        self.index -= 1
                except ValueError:
                    pass
                self.listbox_select(self.index, see=False)
            # if adding from searched list
            elif (self.collected) and (i != self.collection_index
                                       and i != self.collection_index + 1) and self.collection_index != -1:
                item = self.collected[i]
                try:
                    if i > self.collection_index:
                        # delete first then insert for index greater than pivot (collection_index)
                        self.listbox.delete(i)
                        self.collected.remove(self.collected[i])  # remove item
                        self.listbox.insert(self.collection_index + 1, item)
                        self.collected.insert(self.collection_index + 1, item)
                    else:
                        # if index to add is less than the pivot
                        self.listbox.insert(self.collection_index + 1, item)
                        self.collected.insert(self.collection_index + 1, item)
                        self.listbox.delete(i)
                        self.collected.remove(self.collected[i])  # remove item
                        self.collection_index -= 1
                except ValueError:
                    pass
                self.listbox_select(self.collection_index, see=False)

        except IndexError:  # IndexError occurs when nothing was selected in the Listbox
            pass

    def _addto_playlist(self):
        """ function to be called on 'Play Next in Playlist' """

        try:
            i = self.listbox.curselection()[-1]
            self.listbox.selection_clear(0, "end")
            item = self.collected[i]
            num = self._all_files.index(item)

            if item != self._all_files[self.index + 1]:
                try:
                    self._all_files.remove(item)  # remove and insert later
                    # if item removed is above the currently playing in the playlist
                    if num <= self.index:
                        # since we're removing before inserting
                        # removing an item at an index less than self.index
                        # causes list to shift by -1
                        # so our true index becomes self.index - 1
                        self.index -= 1
                except ValueError:
                    pass
                self._all_files.insert(self.index + 1, item)
        except IndexError:
            pass

    # ------------------------------------------------------------------------------------------------------------------------------

    def _listbox_rightclick(self, event):
        """
            Popup event function to bind to local files' listbox right click
        """

        popup = Menu(self.listbox, tearoff=0, bg="gray28", fg="gray97", font=("New Times Roman", 9, "bold"),
                     activebackground="DeepSkyBlue3")
        popup.add_command(label="Play", command=self._on_click)
        if self.collected:
            popup.add_command(label="Play Next Here", command=self._addto_queue)
            # popup.add_separator()
            popup.add_command(label="Play Next in Playlist", command=self._addto_playlist)
        else:
            popup.add_command(label="Play Next", command=self._addto_queue)
        popup.add_separator()
        popup.add_command(label="Refresh Playlist", command=self._on_refresh)
        popup.add_separator()
        popup.add_command(label="Remove from Playlist", command=self._delete_listitem)
        popup.add_command(label="Delete from Storage", command=self._send2trash)
        popup.add_separator()
        popup.add_command(label="Properties", command=self._file_details)

        try:
            popup.tk_popup(event.x_root, event.y_root, 0)
        finally:
            popup.grab_release()

    def _rightclick(self, event):
        """
            Popup event function to bind to main window right click
        """

        popup = Menu(self.main_frame, tearoff=0, bg=Player.BG, fg=Player.FG, font=("New Times Roman", 9),
                     activebackground="DeepSkyBlue3")
        popup.add_command(label="Add to Queue", command=self._select_fav)
        popup.add_command(label="Show Playlist", command=self._listview)
        popup.add_separator()
        popup.add_command(label="Refresh Playlist", command=self._on_refresh)
        try:
            popup.tk_popup(event.x_root, event.y_root, 0)
        finally:
            popup.grab_release()

    def _play_options(self, event):
        """
        pop-up for playback options like 'mute'
        """

        popup = Menu(self._more_btn, tearoff=0, bg="gray97", fg="gray28", font=("New Times Roman", 9, "bold"),
                     activebackground="DeepSkyBlue3", selectcolor="gray28")
        popup.add_checkbutton(label="Mute", variable=self.mute_variable, command=self.mute_mixer)
        popup.add_checkbutton(label="Loop One", variable=self.loopone_variable, command=self._onoff_repeat)
        try:
            popup.tk_popup(event.x_root - 70, event.y_root - 30, 0)
        finally:
            popup.grab_release()

    # ------------------------------------------------------------------------------------------------------------------------------
    def _streams_rightclick(self, event):
        """
            Popup event function to bind to streams listbox right click
        """

        popup = Menu(self.listview, tearoff=0, bg="gray28", fg="gray97", font=("New Times Roman", 9, "bold"),
                     activebackground="DeepSkyBlue3")
        popup.add_command(label="Play", command=self._on_click)
        popup.add_separator()
        popup.add_command(label="Download Audio", command=self.download_audio)
        popup.add_command(label="Download Video", command=self.download_video)
        popup.add_separator()
        popup.add_command(label="Remove from Playlist", command=self._remove_streams)
        popup.add_separator()
        popup.add_command(label="Properties", command=self._url_details)
        try:
            popup.tk_popup(event.x_root, event.y_root, 0)
        finally:
            popup.grab_release()

    def is_downloading(self):
        """ return True if downloading """

        return not self.send_event("is_done")

    # ----------------------------------------------------------------------------------------------------------------------

    def _download_audio(self):
        """ download youtube audio of link """
        # get link from title
        self.status_bar.configure(text="Fetching audio info...")
        title = self.listview.selection_get()
        link = self._title_link.get(title)

        try:
            sinfo = self.get_sinfo(link)
            if sinfo:

                self.audio_streams = tuple(get_audio_streams(sinfo))
                for_display = [f"{i}.    {s.p}    {s.p_size}" for i, s in enumerate(self.audio_streams, start=1)]
                self.status_bar.configure(text="")
                if for_display:
                    quality = getquality(
                        self._root, title,
                        "Audio", for_display,
                        self.download_location
                    )
                    self.prepare_download(quality)
                else:
                    self.status_bar.configure(text="Some data is missing: no audio streams...")
            else:
                self.status_bar.configure(text="Could not fetch audio info...")

        except Exception as e:
            error_msg = handle_yt_errors(e)
            self.status_bar.configure(text=error_msg)

    def download_audio(self):
        """ threaded download audio """
        self.threadpool.submit(self._download_audio)

    def _download_video(self):
        """ download youtube video of link """
        # get link from title
        self.status_bar.configure(text="Fetching video info...")
        title = self.listview.selection_get()
        link = self._title_link.get(title)

        try:
            sinfo = self.get_sinfo(link)
            if sinfo:

                self.video_streams = tuple(get_video_streams(sinfo))
                for_display = [f"{i}.    {s.p}    {s.p_size}" for i, s in enumerate(self.video_streams, start=1)]
                self.status_bar.configure(text="")

                if for_display:
                    quality = getquality(self._root, title,
                                         "Video", for_display, self.download_location)
                    self.prepare_download(quality)
                else:
                    self.status_bar.configure(text="Some data is missing: no video streams...")
            else:
                self.status_bar.configure(text="Could not fetch video info...")

        except Exception as e:
            error_msg = handle_yt_errors(e)
            self.status_bar.configure(text=error_msg)

    def download_video(self):
        """ threaded download video """
        self.threadpool.submit(self._download_video)

    def prepare_download(self, q):

        if q:
            try:
                q, self.download_location, f_preset = q
                index, quality = q.split(".    ")
                index = int(index) - 1  # minus 1 because enumerate starts from 1

                if "kbps" in quality:
                    aud_strm = self.audio_streams[index]
                    self.send_event(
                        "audio_download",
                        aud_strm,
                        self.download_location,
                        preset=f_preset,
                    )
                else:
                    vid_strm = self.video_streams[index]
                    self.send_event(
                        "video_download",
                        vid_strm,
                        self.download_location,
                        preset=f_preset,
                    )
                self.status_bar.configure(text="Added to download queue...")
            except Exception:
                self.status_bar.configure(text="Could not start download...")
            self.threadpool.submit(self.toggle_sleep)

    # ----------------------------------------------------------------------------------------------------------------------

    def _which_tab(self, event):
        """
            Event function to bind to notebook
            gets the tab number
        """

        self.tab_num = int(event.widget.index("current"))
        if self.tab_num:
            # streams tab
            self.searchlabel.configure(text="Search online:")
            ToolTip(self.searchbar, "Search by text\nOr paste a link here\nPress 'enter' to search")
            self._root.geometry(f"318x{self._screen_height}+" + f"{self._root.winfo_x()}+{5}")
            # direct focus to searchbar
            # self.searchbar.focus_set()
        else:
            # local files tab
            self.searchlabel.configure(text="Search:")
            ToolTip(self.searchbar, "Press 'enter' to search")
            self._resize_listbox()

    # ----------------------------------------------------------------------------------------------------------------------

    def _init(self):
        """
            Main window
            Called from self.controls_frame
            or after self.done_frame is set to None
        """

        if self.main_frame is not None:
            self.main_frame.pack_forget()
            self.main_frame = None
        if self.list_frame is not None:
            self.close_playlistwindow()
        self._root.geometry("318x118")
        self._root.config(bg=Player.BG)
        self.main_frame = Frame(self._root, bg=Player.BG, width=318, height=118)
        self.main_frame.pack()
        self.main_frame.bind("<Button-2>", self._rightclick)
        self.main_frame.bind("<Button-3>", self._rightclick)

        self.progress_bar = Scale(self.main_frame, command=self._slide, to=int(self.duration),
                                  variable=self._progress_variable, **self.SCALE_OPTIONS,
                                  style="custom.Horizontal.TScale")

        self.current_time_label = Label(self.main_frame, padx=0, text=self.ftime, width=7, anchor="e",
                                        bg=Player.BG, font=('arial', 9, 'bold'), fg=Player.FG)
        # ----------------------------------------------------------------------------------------------------------------------

        self._title = Label(self.main_frame, pady=0, bg=Player.BG,
                            text=self._title_txt, width=44, height=1,
                            font=('arial', 8, 'bold'), fg=Player.FG, anchor="w")
        self._title.place(x=26, y=1)
        self.playlist_btn = Button(self.main_frame, relief="flat", image=self.rpo_image,
                                   height=15, pady=0, padx=0, bg=Player.BG, command=self._listview)
        self.playlist_btn.place(x=1, y=1)

        self._previous_btn = Button(self.main_frame, padx=0, bg=Player.BG, fg=Player.FG,
                                    command=self._play_prev_command, image=self.previous_img,
                                    relief="groove", width=40, height=40)

        self._play_btn = Button(self.main_frame, padx=0, bg=Player.BG,
                                command=self._play_btn_command, image=self.play_btn_img,
                                fg=Player.FG, relief="groove", width=40, height=40)

        self._next_btn = Button(self.main_frame, padx=0, bg=Player.BG,
                                command=self._play_next_command, image=self.next_img,
                                fg=Player.FG, relief="groove", width=40, height=40)

        self._more_btn = Label(self.main_frame, pady=0, padx=0, bg=Player.BG, width=20,
                               height=15, relief="flat", anchor="w")
        self._more_btn.bind("<ButtonRelease-1>", self._play_options)

        # self.progress_bar.place(x=54, y=98)
        self.check_theme_mode()
        self._update_theme()
        # defaults
        self.current_time_label.configure(text=self.ftime)
        self._title.configure(text=self._title_txt)
        self._play_btn.configure(image=self.play_btn_img)
        # get online streams after the window has loaded

    # ------------------------------------------------------------------------------------------------------------------------------

    def _listview(self):
        """
            Listbox window
            Must be called only from or after self.main_frame
        """
        self.image = PhotoImage(data=images.DARKMORE_IMG)
        if self.main_frame is not None:
            self.main_frame.pack_forget()
            self.main_frame = None
        self._root.config(bg="white smoke")
        self.progress_bar.style = None
        self.controls_frame = Frame(self._root, bg="gray28", width=310, height=94)
        self.controls_frame.pack(fill="both", pady=0)
        # ----------------------------------------------------------------------------------------------------------------------

        self._title = Label(self.controls_frame, pady=0, bg="gray28",
                            text=self._title_txt, width=44, height=1,
                            font=('arial', 8, 'bold'), fg="white", anchor="w")
        self._title.place(x=26, y=1)
        self.playlist_btn = Button(self.controls_frame, relief="flat", image=self.lpo_image,
                                   height=15, pady=0, padx=0, bg="gray28", command=self._init)
        self.playlist_btn.place(x=1, y=1)
        # ---------------------------------------------------------------------------------------------------
        self.current_time_label = Label(self.controls_frame, padx=0, text=self.ftime, width=7, anchor="e",
                                        bg="gray28", font=('arial', 9, 'bold'), fg="white")
        self.current_time_label.place(x=30, y=25)

        self._previous_btn = Button(self.controls_frame, padx=0, bg="gray28", fg="white",
                                    command=self._play_prev_command, image=self.previous_img,
                                    relief="groove")
        self._previous_btn.place(x=100, y=25)

        self._play_btn = Button(self.controls_frame, padx=0, bg="gray28", image=self.play_btn_img,
                                command=self._play_btn_command,
                                fg="white", relief="groove")
        self._play_btn.place(x=150, y=25)

        self._next_btn = Button(self.controls_frame, padx=0, bg="gray28",
                                command=self._play_next_command, image=self.next_img,
                                fg="white", relief="groove")
        self._next_btn.place(x=200, y=25)

        self._more_btn = Label(self.controls_frame, bg="gray28", image=self.image,
                               width=20, height=15, pady=0,
                               relief="flat", anchor="w", padx=0)
        self._more_btn.bind("<ButtonRelease-1>", self._play_options)
        self._more_btn.place(x=245, y=27)

        # set bg for Scale to dark
        self.progressbar_style.configure("custom.Horizontal.TScale", background="gray28")
        self.progress_bar = Scale(self.controls_frame, command=self._slide, to=int(self.duration),
                                  variable=self._progress_variable, **self.SCALE_OPTIONS,
                                  style="custom.Horizontal.TScale")
        self.progress_bar.place(x=46, y=52)

        self.searchlabel = Label(self.controls_frame, font=('arial', 8, 'bold'), text="Search:",
                                 bg="gray28", fg="white", anchor="e", width=23)

        self.searchbar = Entry(self.controls_frame, relief="flat", bg="gray40", fg="white",
                               insertbackground="white")
        self.searchbar.bind("<Return>", self._on_search)
        self.searchbar.bind("<FocusIn>", self.entryhighlight)
        self.searchbar.bind("<KeyRelease>", self.complete_searches)

        # root for notebook
        self.list_frame = Frame(self._root)
        self.list_frame.pack(fill="both", padx=0, pady=0)

        notebook_style = Style()
        try:
            # Import the Notebook.tab element from the default theme
            notebook_style.element_create("Plain.Notebook.tab", "from", "default")
            # Redefine the TNotebook Tab layout to use the new element
            notebook_style.layout(
                "TNotebook.Tab",
                [
                    (
                        'Plain.Notebook.tab', {
                            'children': [
                                (
                                    'Notebook.padding', {
                                        'side': 'top', 'children': [
                                            (
                                                'Notebook.focus', {
                                                    'side': 'top', 'children': [
                                                        ('Notebook.label', {'side': 'top', 'sticky': ''})
                                                    ],
                                                    'sticky': 'nswe'
                                                }
                                            )
                                        ],
                                        'sticky': 'nswe'
                                    }
                                )
                            ],
                            'sticky': 'nswe',
                        }
                    )
                ]
            )
        except Exception:
            pass

        # make the notebook color light
        notebook_style.configure("TNotebook", background="gray28")
        # make the color of dots around a tab same as background
        notebook_style.configure("TNotebook.Tab", font=("", 8, "bold"), focuscolor="white smoke",
                                 foreground="gray60", background="gray28")
        # make bg and fg white smoke and black respectively when selected
        notebook_style.map("TNotebook.Tab", foreground=(("selected", "black"),),
                           background=(("selected", "white smoke"),), font=(("selected", ("", 9, "bold")),))
        book = Notebook(self.list_frame, style="TNotebook")

        # creating frames for grouping other widgets
        self.local_listview = Frame(book, bg="white smoke")
        self.streams_listview = Frame(book, bg="white smoke")
        # adding tabs
        book.add(self.local_listview, text="Local files")
        book.add(self.streams_listview, text="Online streams")
        book.bind("<ButtonRelease-1>", self._which_tab)
        book.pack(fill="both")

        # creating widgets in tabbed frames
        self.listbox = Listbox(self.local_listview, selectmode="extended", **self.LISTBOX_OPTIONS)
        self.scrollbar = Scrollbar(self.local_listview, command=self.listbox.yview)
        self.listbox.config(yscrollcommand=self.scrollbar.set)

        self.listbox.bind("<Double-Button-1>", self._on_click)
        self.listbox.bind("<Button-2>", self._listbox_rightclick)
        self.listbox.bind("<Button-3>", self._listbox_rightclick)
        self.listbox.bind("<MouseWheel>", scroll_widget)
        self.listbox.bind("<Return>", self._on_click)

        self._update_listbox()
        self._update_bindings()
        self.thread_updating_streams()
        if self._playing:
            self.duration_tip = ToolTip(self.progress_bar, f"Duration: {timedelta(seconds=self.duration)}")
        ToolTip(self.searchbar, "Press 'enter' to search")
        if self.isStreaming:
            book.select(1)
            book.event_generate("<ButtonRelease-1>")
        # set search input focused
        # self.searchbar.focus_set()

    # ------------------------------------------------------------------------------------------------------------------------------
    def _handle_stream_tab(self):
        """
            place widgets on streams tab; call after _title_link's been updated
            try connecting and updating streams
        """

        # self.stream_index = -1
        try:
            self.notification.destroy()
            self.reload_button.destroy()
        except AttributeError:
            pass
        try:
            self.listview.destroy()
            self.stream_scrollbar.destroy()
        except AttributeError:
            pass
        self.notification = Label(self.streams_listview,
                                  bg="gray28", fg="white smoke",
                                  text="Fetching...")
        self.notification.pack(padx=30, pady=50)
        # if localhost, no connection
        if self.isOffline and self._title_link is None:
            self.stream_index = -1  # restart index
            # create offline widgets
            self.notification.configure(text="No internet connection")
            self.reload_button = Button(self.streams_listview, text="Refresh", font=("", 8, "underline"),
                                        bg="gray28", fg="white smoke", padx=5, pady=3, command=self.thread_updating_streams)
            self.reload_button.pack(padx=40, pady=1)

        # create listbox; scrollbar and try adding data
        else:
            # if no results to display; try getting it again
            if self._title_link is None:
                self._title_link = self.video_search.search(self.search_str)

            self.listview = Listbox(self.streams_listview, **self.LISTBOX_OPTIONS)
            self.stream_scrollbar = Scrollbar(self.streams_listview, command=self.listview.yview)
            self.listview.config(yscrollcommand=self.stream_scrollbar.set)

            self.listview.bind("<Double-Button-1>", self._on_click)
            self.listview.bind("<MouseWheel>", scroll_widget)
            self.listview.bind("<Button-2>", self._streams_rightclick)
            self.listview.bind("<Button-3>", self._streams_rightclick)
            self.listview.bind("<Return>", self._on_click)
            try:
                self.status_bar.after_cancel(self.progress_loopid)
                self.status_bar.destroy()
            except AttributeError:
                pass

            # if there are online streams
            if self._title_link is not None:
                # status bar
                self.status_bar = Label(self.streams_listview, anchor="e", font=("Consolas", 8, "bold"))
                self.status_bar.pack(fill="x")
                self.progress_loopid = self.status_bar.after(700, self.update_downloader_progress)
                # add items to listview
                self.listview.insert("end", *self._title_link.keys())

                self.listview_select(self.stream_index)
                # when done searching and updating listbox
                # if reload_button was previously packed due to no connection
                try:
                    self.reload_button.destroy()
                # if there's been internet connection from startup; no reload_button
                except AttributeError:
                    pass
                self.notification.destroy()
                # map the listbox and its scrollbar
                self.listview.pack(side="left", padx=3)
                self.stream_scrollbar.pack(side="left", fill="y")
            # if still no results to display
            else:
                self.stream_index = -1
                self.notification.configure(text="Oops! Connected, no internet")
                self.reload_button = Button(self.streams_listview, text="Refresh", font=("", 8, "underline"),
                                            bg="gray28", fg="white smoke", padx=5, pady=3, command=self.thread_updating_streams)
                self.reload_button.pack(padx=40, pady=1)

    # ------------------------------------------------------------------------------------------------------------------------------
    def thread_updating_streams(self):
        self.threadpool.submit(self._handle_stream_tab)

    # ------------------------------------------------------------------------------------------------------------------------------

    def _on_eop(self):
        """
            Done window
            Responsible for end of player dir chooser
        """

        self._playing = 0
        if self.list_frame is not None:
            self.close_playlistwindow()
        if self.main_frame is not None:
            self.main_frame.pack_forget()
            self.main_frame = None
        self._root.geometry("318x118")
        self._root.config(bg="gray94")
        self.done_frame = Frame(self._root, bg="gray94", width=310, height=118)
        self.done_frame.pack(padx=3, pady=5)
        self.repeat_folder_img = PhotoImage(data=images.REPEATFOLDER_IMG)
        self.add_folder_img = PhotoImage(data=images.ADDFOLDER_IMG)

        description = Label(self.done_frame, bg="gray94", width=300,
                            text="  Play Again                 Add New Folder")
        description.pack(side="top", pady=10)
        self.repeat_folder = Button(self.done_frame, image=self.repeat_folder_img,
                                    command=self._repeat_ended, relief="flat")
        self.repeat_folder.pack(padx=70, pady=0, side="left")
        self.add_folder = Button(self.done_frame, image=self.add_folder_img,
                                 command=self._manual_add, relief="flat")
        self.add_folder.pack(padx=0, pady=0, side="left")

    # ------------------------------------------------------------------------------------------------------------------------------

    def __on_click(self):
        """
        plays songs clicked from listbox directly
        """
        change = 0
        try:
            if self.tab_num:  # online streams
                if not self.isOffline:
                    self.stream_index = self.listview.curselection()[-1]
                    # clear text to avoid confusion
                    label_text = self.status_bar["text"]
                    if label_text.startswith(("ERROR", "Error", "Could not")):  # clear if text in tuple
                        self.status_bar.configure(text="")
                    # inform user
                    self.searchlabel.configure(text="Fetching audio...")
                    # get link from title
                    title = self.listview.selection_get()
                    link = self._title_link.get(title)
                    sinfo = self.get_sinfo(link)
                    if sinfo:

                        stream = get_play_stream(sinfo)
                        self._song = stream.url

                        # length in seconds
                        self.duration = stream.length
                        self._title_txt = self._convert(title)
                        self.progress_bar["to"] = int(self.duration)
                        self.isStreaming = 1
                        change = 1
                    else:
                        self.status_bar.configure(text="Could not fetch audio...")
                else:
                    self._title_link = None
                    self.thread_updating_streams()
            else:
                index = self.listbox.curselection()[-1]
                if not self.collected:
                    self._song = self.valid_path(self._all_files[index])
                    self.index = index
                else:
                    self._song = self.valid_path(self.collected[index])
                    self.collection_index = index
                self.isStreaming = 0
                change = 1
            if change:
                self._mixer(self._song).play()
                # wait for media meta to be parsed
                self.threadpool.submit(self._updating)
                self.play_btn_img = self.pause_img
                self._play_btn.configure(image=self.play_btn_img)

        except Exception:
            self.status_bar.configure(text="Could not fetch audio...")

        if self.tab_num:
            self.searchlabel.configure(text="Search online:")
        else:
            self.searchlabel.configure(text="Search:")

    # ------------------------------------------------------------------------------------------------------------------------------

    def _on_click(self, event=None):
        """ Threads __on_click """

        self.change_stream = 0
        self.threadpool.submit(self.__on_click)

    # ------------------------------------------------------------------------------------------------------------------------------

    def _change_place(self):
        """
            Switches slider to above or below
        """

        if self.main_frame is not None:
            if self._slider_above:
                timeandbtn = 94
                pb = 93
                controls = 38
            else:
                timeandbtn = 36
                pb = 34
                controls = 66
            self.progress_bar.place(x=54, y=pb)
            self.current_time_label.place(x=0, y=timeandbtn)
            self._previous_btn.place(x=70, y=controls)
            self._play_btn.place(x=140, y=controls)
            self._next_btn.place(x=210, y=controls)
            self._more_btn.place(x=280, y=timeandbtn)
            self._root.update_idletasks()
            self._slider_above = not self._slider_above

    # ------------------------------------------------------------------------------------------------------------------------------

    def _update_theme(self):
        """
        updates widgets colors
        """

        if self._slider_above:
            timeandbtn = 36
            pb = 34
            controls = 66
        else:
            timeandbtn = 94
            pb = 93
            controls = 38
        if Player.BG == "gray28":
            # make bg color change on hover
            self._update_bindings()
        # Restore slider to previous position
        self._previous_btn.place(x=70, y=controls)
        self._play_btn.place(x=140, y=controls)
        self._next_btn.place(x=210, y=controls)
        self.current_time_label.place(x=0, y=timeandbtn)
        self._more_btn.place(x=280, y=timeandbtn)
        self.progress_bar.place(x=54, y=pb)
        # set bg color for individual widgets
        self.main_frame["bg"] = Player.BG
        self.progressbar_style.configure("custom.Horizontal.TScale", background=Player.BG)
        self._more_btn["bg"], self._more_btn["fg"] = Player.BG, Player.FG
        self._play_btn["bg"], self._play_btn["fg"] = Player.BG, Player.FG
        self._next_btn["bg"], self._next_btn["fg"] = Player.BG, Player.FG
        self._previous_btn["bg"], self._previous_btn["fg"] = Player.BG, Player.FG
        self.current_time_label["bg"], self.current_time_label["fg"] = Player.BG, Player.FG
        self._title["bg"], self._title["fg"] = Player.BG, Player.FG
        self.playlist_btn["bg"] = Player.BG
        self.file_menu["bg"], self.file_menu["fg"] = Player.BG, Player.FG
        self.theme_menu["bg"], self.theme_menu["fg"] = Player.BG, Player.FG
        self.about_menu["bg"], self.about_menu["fg"] = Player.BG, Player.FG
        self.about_menu["selectcolor"] = Player.FG
        self._root.update_idletasks()

    # ------------------------------------------------------------------------------------------------------------------------------

    def _manual_add(self):
        """
            Calls refresher function with open folder set to true
        """

        self._open_folder = 1
        self._refresher()

    # ------------------------------------------------------------------------------------------------------------------------------

    def _repeat_ended(self):
        """
            Repeats playing songs in the just ended folder
        """
        if self.done_frame is not None:
            self.done_frame.pack_forget()
            self.done_frame = None
            self._init()
            self.collection_index = -1
            self.index = -1
            self.on_eos()

    # ------------------------------------------------------------------------------------------------------------------------------

    # @profile_function
    def _refresher(self):
        """
            Updates folder files where necessary, or those passed as CL arguments
            Updates the title of window
            Shuffles the playlist
        """

        self.collection_index = -1
        all_files = []
        if len(PASSED_FILES) > 0:

            self._all_files = self._parse_argfiles(PASSED_FILES)
            f = PASSED_FILES[0]
            self._songspath = f if os.path.isdir(f) else os.path.dirname(f)
            self.download_location = self._songspath
            PASSED_FILES.clear()
            t = os.path.basename(self._songspath) if os.path.basename(self._songspath) else "Disk"
            self._root.title(f"{t} - Lazy Selector")

            # track records
            self.track_records = TrackRecords(TRACK_RDIR, self._songspath)
            return True

        else:

            # try getting the current open folder
            file = Player._CONFIG.get_inner("folders", "last")
            self._songspath = file
            if (self._open_folder) or (not os.path.exists(file)):
                # normalize path
                chosen_dir = os.path.normpath(
                    askdirectory(
                        title="Choose a folder with audio/video files",
                        initialdir=os.path.expanduser("~\\")
                    )
                )
                self._songspath = chosen_dir if chosen_dir != "." else ""  # raise FileNotFoundError below
            # when a user selects the same folder playing again
            if (file == self._songspath) and (self.index < len(self._all_files) - 1):
                # don't update the songs list
                pass
            else:
                # update
                try:
                    all_files = os.listdir(self._songspath)

                except FileNotFoundError:  # if Cancel clicked in the dialog _songspath == ''
                    # if log file isn't empty and the last song had played, update playlist
                    # executes when one clicks cancel on_eop
                    if (file != "") and (self.index >= len(self._all_files) - 1):
                        self._songspath = file
                        all_files = os.listdir(self._songspath)
                    # if no directory was chosen and the last song had not played, no updating playlist
                    elif (file != "") and (self.index <= len(self._all_files) - 1):
                        # avoid 'FileNotFound' error if _songspath remains an empty string
                        self._songspath = file

                    else:
                        answer = okcancel(self._root,
                                          "Lazy Selector",
                                          "\tA folder is required!\nDo you want to select a folder again?"
                                          )
                        if answer:
                            self._open_folder = 1
                            self._refresher()
                        else:
                            self._root.destroy()
                            Player._CONFIG.save()
                            sys.exit(0)
        if len(all_files) > 0:
            self.download_location = self._songspath
            self.index = -1
            # try closing previous nicely
            try:
                self.track_records.close()
            except AttributeError:
                pass
            self.track_records = TrackRecords(TRACK_RDIR, self._songspath)

            Player._CONFIG.update_inner("folders", "last", self._songspath)  # save to config file
            self._all_files = [i for i in all_files if i.endswith(self._supported_extensions)]

            t = os.path.basename(self._songspath) if len(os.path.basename(self._songspath)) != 0 else "Disk"
            self._root.title(f"{t} - Lazy Selector")

            # shuffle(self._all_files)
            with self.track_records.records.transact():  # contxt manager to lock records
                self._all_files.sort(key=self.track_records.sortbykey)

            if self.controls_frame is not None:
                self._update_listbox()
            else:
                if self.done_frame is not None:
                    self.done_frame.pack_forget()
                    self.done_frame = None
                    self._init()

        # check if mixer state is just initialized or ended
        # set player to unloaded, not playing
        if not self._playing and (self.shuffle_mixer.state.value == 6 or self.shuffle_mixer.state.value == 0):
            self.collection_index = -1
            self._uptime = 0
            self._progress_variable.set(self._uptime)
            self.ftime = "00:00"
            self._title_txt = ""
            self.play_btn_img = self.play_img
            self._play_btn_command = self._unpause
            self._play_next_command = None
            self._play_prev_command = None
            try:  # executes when player restarted after ending
                self._play_btn["command"] = self._play_btn_command
                self._previous_btn["command"] = self._play_prev_command
                self._next_btn["command"] = self._play_next_command
                self.current_time_label.configure(text=self.ftime)
                self._title.configure(text=self._title_txt)
                self._play_btn.configure(image=self.play_btn_img)
            except AttributeError:  # on startup; throws an error
                pass
        self._open_folder = 0

    # ------------------------------------------------------------------------------------------------------------------------------

    def valid_path(self, filename):
        """ search for file in the two folder records """
        filepath = os.path.join(self._songspath, filename)
        if not os.path.exists(filepath):
            for folder in self.ALT_DIRS:
                filepath = os.path.join(folder, filename)
                if os.path.exists(filepath):
                    break
        return filepath if os.path.exists(filepath) else ""

    def _loader(self):
        """
            returns the path to song at index
        """

        self.index += 1
        try:
            file = self._all_files[self.index]
        except IndexError:
            return ""

        if (self.controls_frame is not None) and (not len(self.collected)):
            self.listbox_select(self.index)

        return self.valid_path(file)

    def listbox_select(self, index: int, see=True, actvt=True):
        """ select item at index of self.listbox """
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(index)
        if see:
            self.listbox.see(index)
        if actvt:
            self.listbox.activate(index)

    def listview_select(self, index, actvt=True):
        """ select item at index of self.listview """
        if index >= 0:
            self.listview.selection_clear(0, "end")
            self.listview.selection_set(index)
            self.listview.see(index)
            if actvt:
                self.listview.activate(index)

    # ------------------------------------------------------------------------------------------------------------------------------

    def _select_fav(self):
        """
            Asks the user for filenames input
        """

        files_ = askopenfilenames(title="Choose audio/video files",
                                        filetypes=[("All files", "*")],
                                        initialdir=self.FILENAMES_INITIALDIR)
        if files_:
            self.FILENAMES_INITIALDIR = os.path.dirname(files_[0])
            p_files = []
            for loaded_file in files_:
                if loaded_file.endswith(self._supported_extensions):
                    p_files.append(os.path.basename(loaded_file))
                    self.ALT_DIRS.add(os.path.dirname(loaded_file))
            self.load_songsto_playlist(p_files)

    def load_songsto_playlist(self, files: list):
        """ load songs to all_files and update alt_dirs """

        for song in files:
            # remove duplicate song
            try:
                index = self._all_files.index(song)
                self._all_files.remove(song)
                if self.listbox is not None:
                    self.listbox.delete(index)
            except ValueError:  # item not in list
                pass

            self._all_files.insert(self.index + 1, song)
            if self.listbox is not None and (not self.collected):
                self.listbox.insert(self.index + 1, song)
                self._resize_listbox()

    # ------------------------------------------------------------------------------------------------------------------------------

    def _mixer(self, load):
        """
        load media for playback
        """

        # for online streams, set playing to 0 here
        # since the program will take time to fetch stream for slow internet
        self._playing = 0
        try:
            # sometimes the online tab song title will display while playing local file
            # this happens on loading timeout and the play button is clicked for the first time

            if os.path.isfile(load):
                # assume it's a file, otherwise self._title_txt is changed in on_click func
                self._title_txt = self._convert(os.path.splitext(os.path.basename(load))[0])
            self.shuffle_mixer.load(load)
            # preset mute and playback mode
            self.shuffle_mixer.mute(self.mute_variable.get())
            self.shuffle_mixer.loop = self.loopone_variable.get()
            return self.shuffle_mixer
        except Exception:  # handle these exceptions well
            return self.shuffle_mixer

    # ------------------------------------------------------------------------------------------------------------------------------

    def on_eos(self):
        """
            Play on play btn clicked
        """

        self._playing = 0
        self.isStreaming = 0
        self._uptime = 0
        self._progress_variable.set(self._uptime)
        self.play_btn_img = self.pause_img
        self._play_btn.configure(image=self.play_btn_img)

        self._song = self._loader()
        if self._song:
            self._mixer(self._song).play()
            self.threadpool.submit(self._updating)

        if not self._song and not self.index:  # if self.index is 0; play or shuffle btn clicked once
            if self.shuffle_mixer.state.value == 0:
                self._playing = 0

            try:
                # showinfo is blocking
                showinfo(self._root,
                         "Feedback - Lazy Selector",
                         f"{os.path.basename(self._songspath) if len(os.path.basename(self._songspath)) != 0 else 'Disk'} "
                         "folder has no audio/video files.\nChoose a different folder.")
            except AttributeError:  # if self._songspath never initialized
                showinfo(self._root, "Feedback - Lazy Selector", "No folder was selected!")
            # open dir chooser after blocking
            self._manual_add()

        elif not self._song and self.index > len(self._all_files) - 1:
            # _stop_play has no effect if media has finished
            self._stop_play()
            self._on_eop()

    # ------------------------------------------------------------------------------------------------------------------------------

    def update_dur_tooltip(self, t):
        """ update time for duration tooltip """
        try:  # If it's not first time of calling this function
            self.duration_tip.unschedule()
            self.duration_tip.hidetip()
        except AttributeError:
            pass
        self.duration_tip = ToolTip(self.progress_bar, f"Duration: {timedelta(seconds=t)}")

    def _updating(self):
        """
            Helper function; set title; wait for metadata
        """
        self._update_labels("Loading...")
        self._playing = 0
        self._uptime = 0
        self._progress_variable.set(self._uptime)
        t = time()

        while 1:
            try:
                # if data_ready fails try using state
                if self.shuffle_mixer.data_ready or self.shuffle_mixer.state.value == 3:

                    # if tab is local files or nothing was fetched from the internet; probably one's offline
                    if not self.tab_num or self._title_link is None:
                        self.duration = round(self.shuffle_mixer.duration)
                        self.progress_bar["to"] = int(self.duration)

                    self._play_prev_command = lambda: self._play_prev()
                    self._play_next_command = lambda: self._play_prev(prev=0)
                    self._play_btn_command = self._stop_play
                    self._previous_btn["command"] = self._play_prev_command
                    self._play_btn["command"] = self._play_btn_command
                    self._next_btn["command"] = self._play_next_command
                    # _title_txt is defined in _on_click for online streaming; in the mixer func for local files
                    self._update_labels(self._title_txt)
                    # set duration tooltip
                    self.update_dur_tooltip(self.duration)
                    self._playing = 1
                    self.change_stream = 1
                    break
                elif (time() - t) > self.TIMEOUT:
                    self._stop_play()
                    self._title_txt = "Timeout: Could not load media"
                    self._update_labels(self._title_txt)
                    break

            except AttributeError:
                break
            sleep(0.8)

    # ------------------------------------------------------------------------------------------------------------------------------

    def _play_prev(self, prev=1):
        """
            Play previous or next for local files
        """
        if not self.tab_num or self._title_link is None:
            self.play_btn_img = self.pause_img
            self._play_btn.configure(image=self.play_btn_img)
            self._playing = 0
            self._uptime = 0
            self._progress_variable.set(self._uptime)
            if prev:
                if len(self.collected) and self.collection_index > -1:
                    self.collection_index -= 1
                    if self.collection_index < 0:
                        self.collection_index = len(self.collected) - 1
                    i = self.collected[self.collection_index]
                else:
                    self.index -= 1
                    if self.index < 0:
                        self.index = len(self._all_files) - 1
                    i = self._all_files[self.index]
                self._song = self.valid_path(i)
            else:
                if len(self.collected) and self.collection_index > -1:
                    self.collection_index += 1
                    if self.collection_index > len(self.collected) - 1:  # if it's the last item, restart
                        self.collection_index = 0
                    i = self.collected[self.collection_index]
                else:
                    self.index += 1
                    if self.index > len(self._all_files) - 1:
                        self.index = 0
                    i = self._all_files[self.index]
                self._song = self.valid_path(i)

            if self.controls_frame is not None:
                if self.collection_index > -1:
                    prev_index = self.collection_index
                elif self.collection_index == -1 and not len(self.collected):
                    prev_index = self.index
                self.listbox_select(prev_index)  # issue
            self._mixer(self._song).play()
            if self._song:
                # wait for media meta to be parsed
                self.threadpool.submit(self._updating)
        else:
            if self.change_stream and prev:
                self.stream_index -= 1
                self.stream_manager()
            elif self.change_stream and not prev:
                self.stream_index += 1
                self.stream_manager()

    # ------------------------------------------------------------------------------------------------------------------------------

    def _onoff_repeat(self):
        """
        Toggle player 'loop one'
        """

        self.shuffle_mixer.loop = self.loopone_variable.get()

    def mute_mixer(self):
        """ toggle player mute """
        mute = self.mute_variable.get()
        self.shuffle_mixer.mute(mute)

    # ------------------------------------------------------------------------------------------------------------------------------

    def check_theme_mode(self):
        """
            Change playback mode img according to theme set
            Update tooltips
        """
        if self._playing:
            self.duration_tip = ToolTip(self.progress_bar, f"Duration: {timedelta(seconds=self.duration)}")
        if Player.BG == "gray97" and self.main_frame is not None:
            self.rpo_image = PhotoImage(data=images.POINTER_IMG)
            self.more_image = PhotoImage(data=images.MORE_IMG)
        else:
            self.rpo_image = PhotoImage(data=images.DARKPOINTER_IMG)
            self.more_image = PhotoImage(data=images.DARKMORE_IMG)
        self._more_btn.configure(image=self.more_image)
        if self.main_frame is not None:
            self.playlist_btn.configure(image=self.rpo_image)

    # ------------------------------------------------------------------------------------------------------------------------------

    def _release_resources(self):
        """ close the app """

        self.cancel_afters()
        self._root.destroy()
        self.track_records.close()
        self.file_cache.close_cache()
        self.shuffle_mixer.delete()
        self.threadpool.shutdown(wait=False, cancel_futures=True)
        # close aria and downloader
        self.send_event("shutdown_downloader")

    def _kill(self):
        """
            Confirm exit if paused, save modifications
        """
        try:
            try:
                # remove read-only
                os.chmod(os.path.join(DATA_DIR, "lazylog.cfg"), S_IWUSR | S_IREAD)
            except Exception:
                pass
            Player._CONFIG.update_inner("searches", "last", self.search_str)
            Player._CONFIG.update_inner("searches", "all", list(self._search_history))
            is_paused, is_downloading = (self.shuffle_mixer.state.value == 4), self.is_downloading()
            # if mixer paused
            if is_paused or is_downloading:

                msg = f"Music paused: {is_paused}\nDownloading: {is_downloading}\nDo you want to quit anyway?"
                if okcancel(self._root, "Lazy Selector", msg):

                    Player._CONFIG.update_inner("window", "position", f"{self._root.winfo_x()}+{self._root.winfo_y()}")

                    Player._CONFIG.save()
                    # set read-only attr; unsupported from this version onwards
                    # chmod(DATA_DIR + "\\lazylog.cfg", S_IREAD | S_IRGRP | S_IROTH)
                    self._release_resources()
            else:  # if not paused and not downloading
                # pause first
                self._stop_play()

                Player._CONFIG.update_inner("window", "position", f"{self._root.winfo_x()}+{self._root.winfo_y()}")

                Player._CONFIG.save()
                # set read-only attr; unsupported from this version onwards
                # chmod(DATA_DIR + "\\lazylog.cfg", S_IREAD | S_IRGRP | S_IROTH)
                self._release_resources()
        except Exception:
            self._release_resources()

    # ------------------------------------------------------------------------------------------------------------------------------

    def _update_labels(self, song):
        """
            Updates all labels that need update on change of song
            Aligns the title text
        """

        self._title.configure(text=song)

    # ------------------------------------------------------------------------------------------------------------------------------

    def _remove_pref(self):
        """delete prefs"""
        try:
            if self.reset_preferences:
                Player._CONFIG.update_inner("theme", "bg", Player.BG)
                Player._CONFIG.update_inner("theme", "fg", Player.FG)
                self.reset_preferences = 0
            else:
                Player._CONFIG.update_inner("theme", "bg", "gray28")
                Player._CONFIG.update_inner("theme", "fg", "gray97")
                self.reset_preferences = 1
        except Exception:
            pass

    # ------------------------------------------------------------------------------------------------------------------------------
    def _about(self):
        """
            Shows information about the player
        """

        if self.top is None:
            self.top = Toplevel(master=self._root)
            self.top.wm_protocol("WM_DELETE_WINDOW", self._kill_top)
            self.top.wm_title("About - Lazy Selector")
            position = f"{self._root.winfo_x() - 10}+{self._root.winfo_y()}"
            self.top.geometry("355x500+" + position)
            self.top.resizable(0, 0)
            side = "nw"

            def mailto(event):
                subject = f"Lazy Selector Version {__VERSION__}".replace(" ", "%20")
                body = "Hello, Ernesto!".replace(" ", "%20")
                open_tab(f"mailto:?to=ernestondieki12@gmail.com&subject={subject}&body={body}", new=2)

            display_text = Label(self.top, pady=10, padx=50, fg="DeepSkyBlue4",
                                 text=f"Lazy Selector\nVersion: {__VERSION__}\nDeveloped by: Ernesto",
                                 font=("arial", 12, "bold"), relief="groove")
            display_text.pack(pady=10)
            ToolTip(display_text, "Contact the Developer")
            display_text.bind("<ButtonRelease-1>", mailto)
            display_text.bind("<Return>", mailto)
            self.display_canvas = Canvas(self.top, height=400)
            self.top_scrollbar = Scrollbar(self.top, command=self.display_canvas.yview)
            self.display_canvas.config(yscrollcommand=self.top_scrollbar.set)
            self.top_scrollbar.pack(side="right", fill="y")
            self.display_canvas.pack(expand=1)

            def canvas_xy():
                # (39, 3, 373, 195) -> (x1 left, x2 right, y1 top, y2 bottom)
                area = self.display_canvas.bbox("all")
                try:
                    # x1 left, y2 bottom
                    return area[0] + 1, area[3] + 20
                # for the first item, use 40, 10
                except TypeError:
                    return 40, 10

            text_font = ("New Times Roman", 12, "italic")
            self.display_canvas.create_text(
                canvas_xy(),
                text="         This project was intended for own use.",
                anchor="w", font=text_font
            )

            self.portrait_image = PhotoImage(data=images.SOKORO_IMG)
            self.display_canvas.create_text(
                95,  # x
                canvas_xy()[1] + 20,  # y
                text="In loving memory of grandpa, Joseph",
                anchor="w", font=("New Times Roman", 10, "italic bold")
            )
            self.display_canvas.create_image(180, canvas_xy()[1], image=self.portrait_image, anchor=side)
            self.display_canvas.config(scrollregion=self.display_canvas.bbox("all"))
            self.display_canvas.bind("<MouseWheel>", scroll_widget)
            self._root.withdraw()
        # get focus, normal focus_set not working
        self.top.focus_force()

    # ------------------------------------------------------------------------------------------------------------------------------

    def _kill_top(self):
        self._root.deiconify()
        self.top.destroy()
        self.top = None

    # ------------------------------------------------------------------------------------------------------------------------------

    def _update_color(self, bg, fg):
        """
            Switches between themes
            Usage: self._update_color(background:str, foreground:str)
        """

        if self.main_frame is not None:
            Player.BG = bg
            Player.FG = fg
            Player.MN = bg

            if not self.reset_preferences:
                Player._CONFIG.update_inner("theme", "bg", Player.BG)
                Player._CONFIG.update_inner("theme", "fg", Player.FG)
            self.check_theme_mode()
            self._update_theme()

    # ------------------------------------------------------------------------------------------------------------------------------

    def _stop_play(self):
        """
            Pauses playback
        """
        if self._play_btn_command is not None:
            self._playing = 0
            self._play_btn["state"] = "disabled"
            self.play_btn_img = self.play_img
            self._play_btn_command = self._unpause
            self._play_btn.configure(image=self.play_btn_img)
            self._play_btn["command"] = self._play_btn_command
            self.shuffle_mixer.pause()
            self._play_btn["state"] = "normal"
            self.threadpool.submit(self.toggle_sleep)

    def _unpause(self):
        """
            Starts/Resumes playback
        """

        if self._play_btn_command is not None and self.shuffle_mixer.state.value == 4:
            self._play_btn_command = self._stop_play
            self.play_btn_img = self.pause_img
            self._play_btn.configure(image=self.play_btn_img)
            self._play_btn["command"] = self._play_btn_command
            self.shuffle_mixer.play()
            self._playing = 1
        elif self.shuffle_mixer.state.value == 0 or self.shuffle_mixer.state.value == 6:
            self.on_eos()
            self._root.focus_set()
        self.threadpool.submit(self.toggle_sleep)

    # ------------------------------------------------------------------------------------------------------------------------------

    def format_time(self):
        """ format elapsed time for display """
        if self._uptime >= 3600:
            self._root.update_idletasks()
            # string format timedelta

            if self._uptime > 86400:  # if more than a day
                fmt = "{days}d:{hours:02}:{minutes:02}"
            else:
                fmt = "{hours}:{minutes:02}:{seconds:02}"
            return strfdelta(self._uptime, fmt=fmt)
        else:
            mins, secs = divmod(self._uptime, 60)
            return f"{round(mins):02}:{round(secs):02}"

    # ------------------------------------------------------------------------------------------------------------------------------

    def _slide(self, value):
        """
            Seeks and updates value of slider
        """
        # not really DRY, thought of nesting a function but overheads!
        # if playing
        if self._playing:
            self._playing = 0
            value = round(float(value))
            self._progress_variable.set(value)
            self._uptime = self._progress_variable.get()
            # convert to ms
            self.shuffle_mixer.seek(value * 1000)
            self._playing = 1
        # else if paused
        elif self.shuffle_mixer.state.value == 4:
            # self._unpause()
            value = round(float(value))
            self._progress_variable.set(value)
            self._uptime = self._progress_variable.get()
            # convert to ms
            self.shuffle_mixer.seek(value * 1000)
            self.ftime = self.format_time()
            self.current_time_label.configure(text=self.ftime)

    # ------------------------------------------------------------------------------------------------------------------------------

    def _set_uptime(self):
        """
            Updates current time, updates idletasks and checks for eos and battery
        """
        try:
            # attach to existing playlist queue
            playlist_queue = get_q(QUEUE_FILE)
            if playlist_queue:
                self._move_to_songs(playlist_queue)  # this is likely to block
        except Exception:
            pass
        rem_battery = battery.get_state()["percentage"]
        if self._playing:
            # player ended status
            if (self.shuffle_mixer.state.value == 6 and not self.loopone_variable.get()):

                if len(self.collected) > 0 and self.controls_frame is not None and self.collection_index > -1:
                    self.collection_index += 1
                    # self.listbox.selection_clear(0, "end")
                    self._collection_manager()

                elif self.isStreaming and self._title_link is not None and self.tab_num:
                    if self.change_stream:
                        self.stream_index += 1
                        self.stream_manager()
                else:
                    try:
                        f = os.path.join(self._songspath, os.path.basename(self._song))
                        if os.path.exists(f):
                            # add 1 to play frequency
                            self.track_records.log(f)
                    except AttributeError:
                        pass
                    self.on_eos()
                self._root.update_idletasks()
            # playing status
            elif self.shuffle_mixer.state.value == 3:
                self._uptime = round(self.shuffle_mixer.time)
                # format time for display
                self.ftime = self.format_time()
                self.current_time_label.configure(text=self.ftime)

                # duration can change for online streams
                self.duration = round(self.shuffle_mixer.duration)
                # update duration tooltip after every 1 minute
                if (self._uptime % 60 == 0):
                    # set duration tooltip
                    self.update_dur_tooltip(self.duration)
                self.progress_bar.configure(to=int(self.duration))
                self._progress_variable.set(self._uptime)
                self._update_labels(self._title_txt)
                self.progress_bar.update_idletasks()

                if (rem_battery < 16) and not self.lowbatt_notified:
                    # a reminder
                    notification.notify(
                        title="Lazy Selector",
                        message=f'{rem_battery}% Charge Available',
                        app_name="Lazy Selector",
                        app_icon=f"{DATA_DIR}\\app.ico" if os.path.exists(f"{DATA_DIR}\\app.ico") else None
                    )
                    self.lowbatt_notified = 1
            # repeat infinitely until cancelled
            self.uptime_loopid = self._root.after(1000, self._set_uptime)

        else:
            if (rem_battery < 16) and not self.lowbatt_notified:
                # a reminder
                notification.notify(
                    title="Lazy Selector",
                    message=f'{rem_battery}% Charge Available',
                    app_name="Lazy Selector",
                    app_icon=f"{DATA_DIR}\\app.ico" if os.path.exists(f"{DATA_DIR}\\app.ico") else None
                )
                self.lowbatt_notified = 1
            # repeat infinitely until cancelled
            self.uptime_loopid = self._root.after(2000, self._set_uptime)

    # ------------------------------------------------------------------------------------------------------------------------------

    def _collection_manager(self):
        """
            Plays, checks index and loops in searched songs
        """

        self._playing = 0
        if self.collection_index > len(self.collected) - 1:
            self.collection_index = 0
        self.listbox_select(self.collection_index)
        self._on_click()

    def stream_manager(self):
        """
            Plays, checks index and loops in online streams
        """

        self._playing = 0
        # self.listview.selection_clear(0, "end")
        if (self.stream_index > len(self._title_link) - 1) or (self.stream_index < 0):
            self.stream_index = 0
        self.listview_select(self.stream_index)
        self._on_click()
        self.isStreaming = 1

    def _move_to_songs(self, args):
        """ add songs to all_songs and move to play them """
        songs = self._parse_argfiles(args)
        self.load_songsto_playlist(songs)
        self.on_eos()

    def _parse_argfiles(self, args: list[str]) -> list[str]:
        """ parse args and return all files """
        all_files = []
        for arg in args:
            if os.path.isdir(arg):
                self.ALT_DIRS.add(arg)  # keep record of dirs
                all_files.extend(
                    (
                        entry.name
                        for entry in os.scandir(arg)
                        if entry.name.endswith(self._supported_extensions)
                    )
                )
            elif os.path.isfile(arg):
                if arg.endswith(self._supported_extensions):
                    self.ALT_DIRS.add(os.path.dirname(arg))
                    all_files.append(os.path.basename(arg))
        return all_files


PASSED_FILES = sys.argv[1:]


def main_run():
    """ main app run """
    for line in os.popen("tasklist").readlines():
        if line.startswith("Lazy_Selector.exe"):
            running_pid = line.split()[1]
            if running_pid != str(CURRENT_PID):
                # open shared mem; add song to queue
                try:
                    set_q(QUEUE_FILE, PASSED_FILES)
                    break
                except FileNotFoundError:
                    os.popen(f"taskkill /F /PID {running_pid}")

    # if no break occured, start app
    else:
        # create shared mem; wait for song
        with Manager() as shared_manager:
            shared_dict = shared_manager.dict()
            # start downloader process
            downloader = ADownloader(CURRENT_PID, shared_dict)
            downloader.start()

            tk = Tk()
            Player(tk, shared_dict)
            tk.mainloop()


if __name__ == "__main__":
    # freeze support
    freeze_support()
    # DPI aware to avoid blurry text on high DPI screens
    windll.shcore.SetProcessDpiAwareness(1)

    # run main
    main_run()
    sys.exit()
