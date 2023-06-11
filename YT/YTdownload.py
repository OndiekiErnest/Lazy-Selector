__author__ = "Ernesto"
__email__ = "ernestondieki12@gmail.com"


from os import rename
from pytube import YouTube
from threading import Thread
from os.path import splitext, join
from YT.ffmpeg import to_mp3, add_audio, safe_delete


def cvt_bytes(num: float) -> str:
    """ format bytes to respective units for presentation (max GB) """
    try:
        if num >= 1073741824:
            return f"{round(num / 1073741824, 2):,} GB"
        elif num >= 1048576:
            return f"{round(num / 1048576, 2):,} MB"
        elif num >= 1024:
            return f"{round(num / 1024, 2):,} KB"
        else:
            return f"{num} Bytes"
    except Exception:
        return "0 Bytes"


class Base():
    """ Pytube YouTube object, yt_obj """

    def __init__(self, yt: YouTube, display=None, f_type=""):
        self.display = display
        self.yt_obj = yt

        self.yt_obj.register_on_complete_callback(self.on_complete)
        self.yt_obj.register_on_progress_callback(self.on_progress)

        self.stream = None
        self.file_path = ""
        self.display_text = ""
        self._type = f_type

    @property
    def thumbnail(self) -> str:
        """ thumbnail link """
        return self.yt_obj.thumbnail_url

    def _download(self, file_dir, prefix=None):
        """ file_dir: folder to save download """
        file_path = self.stream.download(output_path=file_dir,
                                         max_retries=10,
                                         filename_prefix=prefix,
                                         )
        return file_path

    def update_disp(self, display):
        """ update the label for displaying output """
        self.display = display
        # update text right away
        self.update_text(self.display_text)

    def update_text(self, txt: str):
        """ update display text """
        try:
            self.display_text = txt
            self.display.configure(text=self.display_text)
        except Exception:
            pass

    # obsolete since ThreadPoolExcutor was introduced
    def download(self, path, prefix=None):
        """ Download to `path` folder """
        thread = Thread(target=self._download,
                        args=(path, ), kwargs={"prefix": prefix},
                        daemon=True,
                        )
        thread.start()

    def on_complete(self, stream, filepath):
        self.file_path = filepath

    def on_progress(self, stream, chunk, bytes_rem):
        # stream, chunk, bytes_remaining
        filesize = stream.filesize
        p_done = ((filesize - bytes_rem) / filesize) * 100

        self.update_text(f"({self._type}) {self.filename[:20]}... {round(p_done, 2)}% of {cvt_bytes(filesize)}")


class YTAudio(Base):
    """
    Pytube audio stream of `itag`
    `disp` is of a tkinter Label inst
    """

    def __init__(self, yt: YouTube, itag: int, disp=None, _type="Audio"):

        super().__init__(yt, display=disp, f_type=_type)
        self.stream = self.yt_obj.streams.get_by_itag(itag)
        self.filename = self.stream.default_filename
        self.done = False

    def _download(self, file_dir, prefix=None, preset=None):
        """ override _download method """
        try:
            spd = file_dir.split("\\")
            spd = f"\\{spd[-2]}\\{spd[-1]}" if len(spd) > 1 else f"{spd}\\"
            # over-write if file exists
            self.update_text(f"Downloading to '...{spd}'")

            # download
            file_path = super()._download(file_dir, prefix=prefix)

            path, file_ext = splitext(file_path)

            if file_ext.lower() != ".mp3":
                self.update_text("Converting to mp3...")

                to_mp3(file_path, self.thumbnail, preset=preset)
                safe_delete(file_path)

            self.update_text(f"Saved to '...{spd}'")

        except Exception:
            self.update_text("Error saving the audio. Try again.")
        self.done = True

    def __repr__(self):
        return f"YTAudio, {self.stream.abr}"


class YTVideo(Base):
    """
    Pytube video stream of `itag`
    `disp` is of a tkinter Label inst
    """

    def __init__(self, yt: YouTube, itag: int, disp=None, _type="Video"):
        super().__init__(yt, display=disp, f_type=_type)

        self.done = False

        get_audio = yt.streams.get_audio_only
        # get by itag
        self.stream = self.yt_obj.streams.get_by_itag(itag)
        self.filename = self.stream.default_filename
        self.audio = get_audio(subtype="webm") or get_audio()

    def _download(self, file_dir: str, prefix: str = None, preset=None):
        """
        override _download method
        file_dir: folder to download to
        """

        audio_path = None
        output = join(file_dir, f"{splitext(self.filename)[0]}.mp4")
        spd = file_dir.split("\\")
        spd = f"\\{spd[-2]}\\{spd[-1]}" if len(spd) > 1 else f"{spd}\\"
        # over-write if file exists
        # notify starting
        self.update_text(f"Downloading to '...{spd}'")
        try:

            if self.stream.is_adaptive:
                # download audio in a different thread
                self.thread_audio_download(self.audio.download,
                                           file_dir,
                                           filename_prefix="Audio_",
                                           max_retries=10)
                audio_path = join(file_dir, f"Audio_{self.audio.default_filename}")

            # download video
            self.full_path = super()._download(file_dir, prefix=prefix)

            if (audio_path and self.full_path):

                self.update_text("Combining video and audio...")
                add_audio(self.full_path, audio_path, output, remove_src=True, preset=preset)

            elif audio_path is None:
                # strip 'Video_' prefix
                rename(self.full_path, output)

            self.full_path = output
            self.update_text(f"Saved to '...{spd}'")

        except Exception:
            self.update_text("Error saving the video. Try again.")
        self.done = True

    def thread_audio_download(self, func, *args, **kwargs):
        """ download audio in separate thread """
        thread = Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        thread.start()

    def __repr__(self):
        return f"YTVideo, {self.stream.resolution}"


def get_yt(link: str):
    """ return pytube YouTube instance """
    yt = YouTube(link)
    if yt.age_restricted:
        yt.bypass_age_gate()
    return yt
