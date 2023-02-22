__author__ = "Ernesto"
__email__ = "ernestondieki12@gmail.com"


from tkinter import (
    Toplevel,
    Button,
    Label,
    Frame,
    Radiobutton,
    StringVar,
    Canvas,
    Scrollbar,
)
from tkinter.filedialog import askdirectory
from tkinter.ttk import Button as tButton, Combobox
try:
    from idlelib.tooltip import ToolTip
# for python greater than 3.7
except ImportError:
    from idlelib.tooltip import Hovertip as ToolTip
from os.path import normpath


PRESETS = ("ultrafast", "superfast",
           "veryfast", "faster", "fast", "medium",
           "slow", "slower", "veryslow")
PRESET_TIP = """Presets for post-download processing
Slower preset takes longer to complete
and the final file size is likely to be smaller"""


def scroll_widget(event):
    """ event function to bind to mouse wheel """
    event.widget.yview_scroll(int(-1 * (event.delta / 120)), "units")


def singleton(cls):
    """
    decorator function
    destroy previously opened window,
    opens a new one with `args` and `kwargs`
    """
    instance = [None]

    def wrapper(*args, **kwargs):

        if isinstance(instance[0], Toplevel):  # Toplevel in this case is StreamsPopup
            # clear select_var then close
            instance[0].on_close()
            # instance.clear()

        instance[0] = cls(*args, **kwargs)
        return instance[0]

    return wrapper


class PathInput(Frame):

    def __init__(self, master, init_dir: str, **kwargs):
        super().__init__(master, **kwargs)
        self.root = master
        self.init_dir = init_dir

        dir_choose = Button(self, text="Browse", font=("", 7), command=self.choose,
                            height=1,
                            bg="gray20", fg="white")
        ToolTip(dir_choose, "Choose folder to download to", hover_delay=0)
        dir_choose.pack(side="left", padx=0)

        self.dir_label = Label(self, text=self.init_dir, font=("", 8, "italic"),
                               width=43, anchor="e", borderwidth=2, relief="ridge",
                               bg="white")
        self.dir_label.pack(side="left", padx=0)
        self.update()

    def choose(self):
        path = normpath(askdirectory(title="Choose folder to Download to",
                                     initialdir=self.init_dir)
                        )
        if path != ".":
            self.init_dir = path
            self.dir_label.configure(text=path)
            self.update()


@singleton
class StreamsPopup(Toplevel):

    def __init__(self, master, title, f_type, streams, idir, **kwargs):

        super().__init__(master, highlightbackground="gray20", **kwargs)
        self.root = master

        self.title(title)
        self.geometry(f"300x300+{self.root.winfo_x() + 2}+{self.root.winfo_y() + 514}")
        # prevent flashing of this window in a different pos
        self.update()
        self.wm_transient(self.root)
        self.configure(bg="white")
        self.wm_protocol("WM_DELETE_WINDOW", self.on_close)

        self.select_var = StringVar(master=self, value=" ")
        self.select_var.trace_add(("write", "unset"), self.changebtnstate)
        # the following are not scrollable:
        # title label, ok btn, path_area, preset area
        self.title = Label(self, text=f"Choose {f_type} Quality to Download",
                           font=("arial", 11, "bold underline"), pady=3,
                           bg="white")
        self.title.pack(side="top", fill="x")
        # download button
        self.ok = Button(self, text="Download", state="disabled",
                         bg="gray20", fg="white", command=self.destroy)
        self.ok.pack(side="bottom", pady=10)
        # add ffmpeg preset area
        self.dropmenu_var = StringVar()
        self.dropmenu_var.set("medium")

        dropdown_menu = Combobox(self, textvariable=self.dropmenu_var,
                                 justify="center", values=PRESETS, state="readonly",
                                 background="white")
        ToolTip(dropdown_menu, PRESET_TIP, hover_delay=0)
        dropdown_menu.pack(side="bottom", fill="x")
        # download path area
        self.path_area = PathInput(self, idir)
        self.path_area.pack(side="bottom", anchor="center", fill="x")

        # create a canvas and a vertical scrollbar for scrolling it
        vscrollbar = Scrollbar(self, orient="vertical")
        vscrollbar.pack(side="right", fill="y")
        self.canvas = Canvas(self, bd=0,
                             height=350,  # starting height
                             highlightthickness=0,
                             yscrollcommand=vscrollbar.set,
                             bg="white")
        # bind to mouse scrolls
        self.canvas.bind("<MouseWheel>", scroll_widget)

        self.canvas.pack(side="left", fill="both", expand=True)
        vscrollbar.configure(command=self.canvas.yview)

        # create a frame inside the canvas which will be scrolled with it
        self.interior = Frame(self.canvas, **kwargs)
        self.canvas.create_window(0, 0, window=self.interior, anchor="nw")

        for stream in streams:
            radiobtn = Radiobutton(self.interior, variable=self.select_var, anchor="w",
                                   value=stream, text=stream, bg="white")
            radiobtn.pack(fill="x")
        # update scroll region
        self.set_scrollregion()
        # reset the view
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def set_scrollregion(self, event=None):
        """ set the scroll region of the canvas"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def changebtnstate(self, *args):
        try:
            if args[2] == "write":
                self.ok.configure(state="normal")
            elif args[2] == "unset":
                self.ok.configure(state="disabled")
        except Exception:
            pass

    def on_close(self):
        """ clear variable on window close """
        self.select_var.set(" ")
        self.destroy()
        del self


class _Base(Toplevel):

    def __init__(self, master, title, **kwargs):

        super().__init__(master=master, highlightbackground="gray20", **kwargs)
        self.master = master

        self.details_expanded = False
        self.title(title)  # win title
        self.geometry(f"314x116+{self.master.winfo_x() + 2}+{self.master.winfo_y() + 35}")
        # prevent flashing of this window in a different pos
        self.update()
        self.configure(bg="white")
        self.wm_transient(self.master)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        # create widgets
        self.create_widgets()

    def create_widgets(self):
        self.grab_set()
        self.okay_btn.focus_set()
        self.okay_btn.bind("<Return>", self.okay)

    def okay(self, event=None):
        self.grab_release()
        self.destroy()
        self.choice = True

    def cancel(self, event=None):
        self.grab_release()
        self.destroy()


class Quiz(_Base):

    def __init__(self, master, title, quiz, **kwargs):

        self.master = master
        self.quiz = quiz
        self.choice = False
        super().__init__(master, title, **kwargs)

    def create_widgets(self):
        Label(self, image="::tk::icons::question", font=("", 9), bg="white").grid(row=0, column=0, pady=7, padx=5, sticky="w")
        Label(self, text=f"{self.quiz}", bg="white").grid(row=0, column=1, columnspan=2, pady=7, sticky="w")
        self.okay_btn = tButton(self, text="OK", command=self.okay)
        self.okay_btn.grid(row=1, column=1, sticky="e")
        self.cancel_btn = tButton(self, text="Cancel", command=self.cancel)
        self.cancel_btn.bind("<Return>", self.cancel)
        self.cancel_btn.grid(row=1, column=2, padx=7, sticky="e")
        super().create_widgets()


class Info(_Base):

    def __init__(self, master, title, msg, **kwargs):

        self.master = master
        self.msg = msg
        self.choice = True
        super().__init__(master, title, **kwargs)

    def create_widgets(self):
        Label(self, image="::tk::icons::information", font=("", 9), bg="white").grid(row=0, column=0, pady=7, padx=5, sticky="w")
        Label(self, text=f"{self.msg}", bg="white").grid(row=0, column=1, columnspan=2, pady=7, sticky="w")
        self.okay_btn = tButton(self, text="OK", command=self.cancel)
        self.okay_btn.grid(row=1, column=2, padx=7, sticky="e")
        super().create_widgets()


def getquality(master, title, f_type, streams, idir, **kwargs):
    win = StreamsPopup(master, title, f_type, streams, idir, **kwargs)
    win.wait_window()
    selected_q = win.select_var.get()
    selected_preset = win.dropmenu_var.get()
    if (len(selected_q) > 1) and (selected_preset):
        return selected_q, win.path_area.init_dir, selected_preset
    return ()


def showinfo(master, title, msg, **kwargs):
    win = Info(master, title, msg, **kwargs)
    win.wait_window()
    # return win.choice


def okcancel(master, title, quiz, **kwargs):
    win = Quiz(master, title, quiz, **kwargs)
    win.wait_window()
    return win.choice
