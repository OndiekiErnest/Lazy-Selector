""" youtube download functionalities """

from ffmpeg_progress_yield import FfmpegProgress
from collections import namedtuple
from YT.ffmpeg import (
    ffmpeg_audio_download,
    ffmpeg_dash_download,
    ffmpeg_video_download,
    FFPROBE_PATH,
)
from datetime import (
    datetime,
)
from subprocess import (
    STARTUPINFO,
    STARTF_USESHOWWINDOW,
)
import os
import re
import yt_dlp
import humanize


AudioStream = namedtuple(
    "AudioStream",
    (
        "url",
        "title",
        "thumbnail",
        "length",
        "p_size",
        "p",
        "info",
    ),
)

VideoStream = namedtuple(
    "VideoStream",
    (
        "url",
        "title",
        "audio",
        "length",
        "p_size",
        "p",
        "info",
    ),
)

RES_MAP = {
    "144p": "(LOWEST)",
    "240p": "(LOWER)",
    "360p": "(LOW)",
    "480p": "(SD)",
    "720p": "(HD)",
    "1080p": "(FHD)",
    "1440p": "(2K)",
    "2160p": "(4K)",
    "2880p": "(5K)",
    "4320p": "(8K)",
}
VID_FILTER = set(RES_MAP.keys())


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


def _is_validvid(item: dict):
    """ return true if stream is valid video """
    width = item.get("width")
    f = item.get("format_note")
    container = item.get("container")
    is_hls = item.get("format_id", "None").startswith("hls")
    yt_valid = (width and container and (f in VID_FILTER))
    return yt_valid or is_hls


def _filter_vids(sinfo: list[dict]) -> list:
    """ return only vids or empty array """
    vids = sorted(
        (s for s in sinfo if _is_validvid(s)),
        key=video_sortkey,
        reverse=True,
    )
    return vids


def _filter_auds(sinfo: list[dict]) -> list:
    """ return only audio or empty array """
    auds = sorted(
        (s for s in sinfo if (s.get("abr"))),
        key=audio_sortkey,
        reverse=True,
    )
    return auds


def get_url_details(sinfo: dict, only=None):
    """
    extract necessary data for display in properties
    sinfo is a dict
    """

    try:
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
                "filesize": humanize.naturalsize(sinfo.get('filesize_approx', 0) or 0),
                "uploader": sinfo.get("uploader"),
                "uploaded": humanize.naturaltime(upload_date),
                "live": f"{sinfo.get('is_live', False) or False}",
                "streamed": f"{sinfo.get('was_live', False) or False}",
                "availability": sinfo.get("availability"),
                "age": f'{sinfo.get("age_limit", 0)}+',
                "audio": f"{sinfo.get('audio_channels')} channels, {sinfo.get('abr') or 0} kbps, {sinfo.get('asr') or 0:,} Hz",
                "fps": sinfo.get("fps"),
                "categories": "\n".join(sinfo.get("categories", [])),
            }
        else:
            return sinfo.get(only)
    except TypeError:

        return {
            "thumbnail": sinfo.get("thumbnail"),
            "url": sinfo.get("original_url") or sinfo.get("webpage_url"),
            "duration": sinfo.get("duration_string"),
            "age": f'{sinfo.get("age_limit", 0)}+',

        }


def yt_audstream(item: dict, title, thumbnail_url, duration):
    """ create and return AudioStream """
    media_url = item.get("url")
    bitrate = round(item.get("abr", 0) or 0)  # take care of live items that return None
    filesize = item.get("filesize", 0) or 0
    p_size = humanize.naturalsize(filesize) if filesize else ""
    p = f"{bitrate} kbps"

    return AudioStream(
        media_url,
        title,
        thumbnail_url,
        duration,
        p_size,
        p,
        item,
    )


def get_best_audio(sinfo: dict):
    """
    extract necessary audio data from url info
    sinfo is sanitized info dict
    """

    title = normalize_filename(sinfo.get("title", ""))
    duration = sinfo.get("duration", 0)
    thumbnail = sinfo.get("thumbnail")

    streams = _filter_auds(sinfo.get("formats"))
    if streams:
        return yt_audstream(streams[0], title, thumbnail, duration)


def get_audio_streams(sinfo: dict):
    """ extract necessary audio data from info dict """

    try:

        title = normalize_filename(sinfo.get("title", ""))
        duration = sinfo.get("duration", 0)
        thumbnail = sinfo.get("thumbnail")

        aud_streams = _filter_auds(sinfo.get("formats"))
        for item in aud_streams:

            yield yt_audstream(item, title, thumbnail, duration)

    except Exception:
        yield


def get_video_streams(sinfo: dict):
    """ extract necessary video data from info dict """
    # https://www.pornhub.com/view_video.php?viewkey=645b22e6cce3b
    try:
        title = normalize_filename(sinfo.get("title", ""))
        audio_stream = get_best_audio(sinfo)  # get the best audio stream or None
        duration = sinfo.get("duration", 0)

        vid_streams = _filter_vids(sinfo.get("formats"))

        for item in vid_streams:

            res = item.get("format_note")

            url = item.get("url")
            filesize = item.get("filesize", 0) or 0
            p_size = humanize.naturalsize(filesize) if filesize else ""
            p = f"{item.get('format')} {RES_MAP.get(res, '')}"  # presentation

            yield VideoStream(
                url,
                title,
                audio_stream,
                duration,
                p_size,
                p,
                item,
            )

    except Exception as e:
        print(e)
        yield


def get_play_stream(sinfo: dict):
    """ return audio for streaming, if None, return video stream """
    aud = get_best_audio(sinfo)
    if aud:
        return aud
    return next(get_video_streams(sinfo))  # get video stream if no audio stream


class Downloader():
    """ audio/video download manager """

    def __init__(self, stream, display, dst):
        self.display_label = display
        self.process = None
        self.dst = dst
        self.stream = stream
        self.done = False
        self.disp_title = f"{self.stream.title[:15]}...{self.stream.title[-3:]}"
        self.disp_size = self.stream.p_size

    def ffmpeg_process(self, cmd):
        """ run ffmpeg while getting the progress """
        # create NOWINDOW subprocess flags
        s = STARTUPINFO()
        s.dwFlags |= STARTF_USESHOWWINDOW
        # print(cmd)

        self.process = FfmpegProgress(cmd, ffprobe_path=FFPROBE_PATH)
        for progress in self.process.run_command_with_progress(popen_kwargs={'startupinfo': s}):
            yield progress

    def update_disp(self, display):
        """ update display label """
        self.display_label = display

    def on_progress(self, progress, prefix):
        """ update progress """
        dsp_txt = f"({prefix}) {self.disp_title}: {progress}% of {self.disp_size or '?'}  "
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

    def video_download(self, dst_path, prefix=None, preset=None, sinfo=None):
        """ video download function """
        self.display_label.config(text="Downloadig Video...")
        filename = os.path.join(dst_path, f"{self.stream.title}.mp4")

        try:
            if not self.stream.audio:
                downloader = ffmpeg_video_download(
                    self.stream.url,
                    filename,
                    preset=preset,
                    func=self.ffmpeg_process,
                    stream=self.stream.info,
                    info_dict=sinfo,
                )
            else:
                downloader = ffmpeg_dash_download(
                    self.stream.url,
                    self.stream.audio.url,  # audio stream
                    filename,
                    preset=preset,
                    func=self.ffmpeg_process,
                    stream=self.stream.info,
                    info_dict=sinfo,
                )
            for progress in downloader:
                self.on_progress(progress, prefix)  # update progress
            self.on_done(dst_path)

        except Exception:
            self.display_label.config(text="An error occured while downloading...")
        self.done = True

    def audio_download(self, dst_path, prefix=None, preset=None, sinfo=None):
        """ audio download function """
        self.display_label.config(text="Downloadig Audio...")
        filename = os.path.join(dst_path, f"{self.stream.title}.mp3")

        try:
            downloader = ffmpeg_audio_download(
                self.stream.url,
                self.stream.thumbnail,  # audio cover link
                filename,
                preset=preset,
                func=self.ffmpeg_process,
                stream=self.stream.info,
                info_dict=sinfo,
            )
            for progress in downloader:
                self.on_progress(progress, prefix)  # update progress
            self.on_done(dst_path)
        except Exception as e:
            print(e)
            self.display_label.config(text="An error occured while downloading...")
        self.done = True

    def cancel_download(self):
        if self.process:
            try:
                self.process.quit_gracefully()
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
