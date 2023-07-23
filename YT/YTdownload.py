""" youtube download functionalities """

from ffmpeg_progress_yield import FfmpegProgress
import os
from collections import namedtuple
from YT.ffmpeg import (
    ffmpeg_audio_download,
    ffmpeg_dash_download,
)
import re
import yt_dlp
from datetime import datetime
import humanize
from YT.utils import (
    prevent_sleep,
    release_sleep,
)


AudioStream = namedtuple(
    "AudioStream",
    (
        "url", "thumbnail",
        "title", "itag",
        "abr", "asr",
        "filesize", "container",
        "length",
        "p",
    ),
)
VideoStream = namedtuple(
    "VideoStream",
    (
        "url", "thumbnail",
        "title", "itag",
        "res", "filesize",
        "container",
        "audio",
        "p",
    ),
)
RES_MAP = {
    "480p": "(SD)",
    "720p": "(HD)",
    "1080p": "(FHD)",
    "1440p": "(2K)",
    "2160p": "(4K)",
    "2880p": "(5K)",
    "4320p": "(8K)",
}


def normalize_filename(name):
    """ remove invalid characters for filename """
    return re.sub(r'[<>:"/\\|?*]', "", name)


def audio_sortkey(item):
    """ sort based on bitrate """
    abr = item.get("abr", 0)
    return abr if abr else 0


def video_sortkey(item):
    """
    sort based on video width and size
    width and size must be int
    """
    width = item.get("width", 0) or 0
    size = item.get("filesize", 0) or 0
    return (width, -size)  # negate size, to sort in opposite order


def get_url_details(sinfo: dict, only=None):
    """
    extract necessary data for display in properties
    sinfo is a dict
    """

    if only is None:
        upload_date = datetime.strptime(sinfo.get("upload_date"), "%Y%m%d")
        return {
            "thumbnail": sinfo.get("thumbnail"),
            "url": sinfo.get("original_url") or sinfo.get("webpage_url"),
            "resolution": sinfo.get("resolution"),
            "views": f"{sinfo.get('view_count', 0):,}",
            "likes": f"{sinfo.get('like_count', 0):,}",
            "comments": f"{sinfo.get('comment_count') or 0:,} comments",
            "duration": sinfo.get("duration_string", 0),
            "filesize": humanize.naturalsize(sinfo.get('filesize_approx', 0)),
            "uploader": sinfo.get("uploader"),
            "uploaded": humanize.naturaltime(upload_date),
            "live": f"{sinfo.get('is_live', False) or False}",
            "streamed": f"{sinfo.get('was_live', False) or False}",
            "availability": sinfo.get("availability"),
            "age": sinfo.get("age_limit"),
            "audio": f"{sinfo.get('audio_channels')} channels, {sinfo.get('abr') or 0} kbps, {sinfo.get('asr') or 0:,} Hz",
            "fps": sinfo.get("fps"),
            "categories": ", ".join(sinfo.get("categories", [])),
        }
    else:
        return sinfo.get(only)


def get_best_audio(sinfo: dict):
    """
    extract necessary audio data from url info
    sinfo is sanitized info dict
    """

    title = normalize_filename(sinfo.get("title", ""))
    thumbnail_url = sinfo.get("thumbnail")
    duration = sinfo.get("duration", 0)

    stream = sorted(
        sinfo.get("formats"),
        key=audio_sortkey,
        reverse=True
    )[0]

    media_url = stream.get("url")
    itag = stream.get("format_id")
    bitrate = round(stream.get("abr", 0) or 0)  # take care of live streams that return None
    asr = stream.get("asr")
    filesize = humanize.naturalsize(stream.get("filesize", 0))
    container = stream.get("container")
    p = f"{bitrate} kbps"

    return AudioStream(
        media_url,
        thumbnail_url,
        title,
        itag,
        bitrate,
        asr,
        filesize,
        container,
        duration,
        p,
    )


def get_audio_streams(sinfo: dict):
    """ extract necessary audio data from info dict """

    try:
        title = normalize_filename(sinfo.get("title", ""))
        thumbnail_url = sinfo.get("thumbnail")
        duration = sinfo.get("duration", 0)

        streams = sorted(
            sinfo.get("formats"),
            key=audio_sortkey,
            reverse=True
        )
        for item in streams:

            if item.get("abr"):  # audio

                media_url = item.get("url")
                itag = item.get("format_id")
                bitrate = round(item.get("abr", 0) or 0)  # take care of live streams that return None
                asr = item.get("asr")
                filesize = humanize.naturalsize(item.get("filesize", 0))
                container = item.get("container")
                p = f"{bitrate} kbps"

                yield AudioStream(
                    media_url,
                    thumbnail_url,
                    title,
                    itag,
                    bitrate,
                    asr,
                    filesize,
                    container,
                    duration,
                    p,
                )

    except Exception:
        yield ()


def get_video_streams(sinfo: dict):
    """ extract necessary video data from info dict """

    try:
        title = normalize_filename(sinfo.get("title", ""))
        thumbnail = sinfo.get("thumbnail")
        audio_stream = get_best_audio(sinfo)  # get the best audio stream

        streams = sorted(
            sinfo.get("formats"),
            key=video_sortkey,
            reverse=True
        )
        for item in streams:

            res = item.get("format_note")
            container = item.get("container")

            if (item.get("width")) and (res) and (container):  # video
                url = item.get("url")
                itag = item.get("format_id")
                filesize = humanize.naturalsize(item.get("filesize", 0))
                p = f"{res} {RES_MAP.get(res, '')}"  # presentation

                yield VideoStream(
                    url,
                    thumbnail,
                    title,
                    itag,
                    res,
                    filesize,
                    container,
                    audio_stream,
                    p,
                )

    except Exception:
        yield ()


class Downloader():
    """ audio/video download manager """

    def __init__(self, stream, display, dst):
        self.display_label = display
        self.process = None
        self.dst = dst
        self.stream = stream
        self.done = False
        self.disp_title = self.stream.title[:17]

    def ffmpeg_process(self, cmd):
        """ run ffmpeg while getting the progress """
        self.process = FfmpegProgress(cmd)
        for progress in self.process.run_command_with_progress():
            yield progress

    def update_disp(self, display):
        """ update display label """
        self.display_label = display

    def on_progress(self, progress, prefix):
        """ update progress """
        dsp_txt = f"({prefix}) {self.disp_title}...  {progress}% of {self.stream.filesize}  "
        try:
            self.display_label.config(text=dsp_txt)
        except Exception:  # when display is destroyed
            pass

    def on_done(self, dst_path):
        """ send a message about download location """

        sep = os.sep
        spd = dst_path.split(sep)
        spd = f"{sep}{spd[-2]}{sep}{spd[-1]}" if len(spd) > 1 else f"{spd[0]}{sep}"

        self.display_label.config(text=f"Downloaded to '{spd}'...")

    def video_download(self, dst_path, prefix=None, preset=None):
        """ video download function """
        self.display_label.config(text="Downloadig Video...")
        filename = os.path.join(dst_path, f"{self.stream.title}.mp4")
        # prevent sys sleep
        prevent_sleep()
        try:
            downloader = ffmpeg_dash_download(
                self.stream.url,
                self.stream.audio.url,  # audio stream
                filename,
                preset=preset,
                func=self.ffmpeg_process,
            )
            for progress in downloader:
                self.on_progress(progress, prefix)  # update progress
            self.on_done(dst_path)
        except Exception:
            self.display_label.config(text="An error occured while downloading...")
        self.done = True
        # release sleep lock
        release_sleep()

    def audio_download(self, dst_path, prefix=None, preset=None):
        """ audio download function """
        self.display_label.config(text="Downloadig Audio...")
        filename = os.path.join(dst_path, f"{self.stream.title}.mp3")
        # prevent sys sleep
        prevent_sleep()
        try:
            downloader = ffmpeg_audio_download(
                self.stream.url,
                self.stream.thumbnail,  # audio cover link
                filename,
                preset=preset,
                func=self.ffmpeg_process,
            )
            for progress in downloader:
                self.on_progress(progress, prefix)  # update progress
            self.on_done(dst_path)
        except Exception:
            self.display_label.config(text="An error occured while downloading...")
        self.done = True
        # release sleep lock
        release_sleep()

    def cancel_download(self):
        if self.process:
            try:
                self.process.quit()
            except RuntimeError:
                pass  # no process
        self.done = True
        return self.done


def get_sanitizedinfo(url: str) -> dict:
    """ extract and get yt sanitized info from url """
    try:
        with yt_dlp.YoutubeDL() as yt:
            info = yt.extract_info(url, download=False)
            return yt.sanitize_info(info)
    except Exception:
        return {}
