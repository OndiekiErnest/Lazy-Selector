<<<<<<< HEAD
""" streams-level utils """

from datetime import (
    timedelta,
    datetime,
    timezone,
)
from urllib.parse import urlparse
import os
import sys
import ctypes
import mutagen
import humanize
import exiftool

# system sleep inhibit/release constants
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

INHIBIT = ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED
RELEASE = ES_CONTINUOUS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def prevent_sleep():
    """ prevent the system from sleeping """
    try:
        # Windows
        ctypes.windll.kernel32.SetThreadExecutionState(INHIBIT)
    except Exception:
        pass


def allow_sleep():
    """ release the sleep lock """
    try:
        # Windows
        ctypes.windll.kernel32.SetThreadExecutionState(RELEASE)
    except Exception:
        pass


def r_path(relpath, base_dir=BASE_DIR) -> str:
    """ get absolute path, when running file or frozen """

    base_path = getattr(sys, "_MEIPASS", base_dir)
    abs_path = os.path.join(base_path, relpath)
    return abs_path if os.path.exists(abs_path) else base_dir


def is_url(url: str) -> bool:
    """ return if url is valid """
    try:
        result = urlparse(url.strip())
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def strfdelta(secs, fmt="{days}:{hours}:{minutes:02}:{seconds:02}") -> str:
    """ create timedelta from secs, string format timedelta """
    tdelta = timedelta(seconds=secs)
    d = {"days": tdelta.days}
    d["hours"], rem = divmod(tdelta.seconds, 3600)
    d["minutes"], d["seconds"] = divmod(rem, 60)
    return fmt.format(**d)


def fmt_seconds(secs) -> str:
    """ return formatted time as H:M:S """
    days, rem = divmod(round(secs), 86400)
    hours, rem = divmod(round(rem), 3600)
    minutes, seconds = divmod(round(rem), 60)

    fmt = ""
    if days:
        fmt = f"{days}d:"
    if hours:
        fmt = f"{fmt}{hours:02}:"
    if minutes:
        fmt = f"{fmt}{minutes:02}:"
    if seconds:
        fmt = f"{fmt}{round(seconds):02}"
    else:
        fmt = "00:00"
    return fmt


def from_exiftool(file: str, ex_path: str) -> dict:
    """ get metadata as dict using exiftool """
    try:
        with exiftool.ExifToolHelper(executable=ex_path, common_args=None, encoding="utf-8") as et:
            data = et.get_metadata(file)[0]
            channels = data.get("ChannelMode") or f'{data.get("AudioChannels")} channels'
            sr = data.get("OutputAudioSampleRate") or data.get("AudioSampleRate")

            try:
                cleaned = {
                    "duration": f'{data.get("Duration", " ")}'.split(" ")[0],
                    "mimetype": data.get("MIMEType"),
                    "audio": f'{channels}, {sr:,} Hz',
                    "permissions": data.get("FilePermissions"),
                    "resolution": data.get("ImageSize"),
                    "fps": data.get("VideoFrameRate"),
                }
            except Exception:
                cleaned = {
                    "mimetype": data.get("MIMEType"),
                    "audio": f"{channels}, {data.get('SampleRate')} Hz"
                }
            return cleaned

    except Exception:
        return {}


def file_details(filename, exiftool_path=None):
    """ get local file metadata """
    try:
        meta = None
        dt = datetime.fromtimestamp(os.path.getctime(filename), tz=timezone.utc)
        c_human = humanize.naturaltime(dt)
        try:
            file: mutagen.FileType = mutagen.File(filename)

            if file:  # is not None
                info = file.info
                cover = file.tags.getall("APIC")
                if cover:
                    thumb_data = cover[0].data
                else:
                    thumb_data = None
                meta = {
                    "thumbnail": thumb_data,  # data or None
                    "duration": fmt_seconds(info.length),
                    "audio": f"{info.channels} channels, {info.bitrate / 1000} kbps, {info.sample_rate:,} Hz",
                }
            else:
                meta = from_exiftool(filename, exiftool_path)
        except Exception:
            meta = from_exiftool(filename, exiftool_path)

        offline = {
            "path": os.path.dirname(filename),
            "type": f"{os.path.splitext(filename)[1].strip('.').upper()} File",
            "filesize": humanize.naturalsize(os.path.getsize(filename)),
            "created": f"{c_human} ({dt.strftime('%d %b %Y')})",
        }
        if meta:
            offline.update(meta)

        # if no external, get offline
        return offline

    except Exception:
        return {}


def safe_delete(filename: str):
    """ skip exceptions that may occur when deleting """
    try:
        os.remove(filename)
    except Exception:
        pass


def _datefromstring(date: str, fmt="%Y:%m:%d %H:%M:%S%z") -> str:
    """ parse datetime from string """
    dt = datetime.strptime(date, fmt)
    fmtd = f"{humanize.naturaltime(dt)} ({dt.strftime('%d %b %Y')})"
    return fmtd


def _callback(value: str) -> str:
    """ callaback function for dict routing """
    return value


def _format_values(key: str, value: str):
    routes = {
        "FileCreateDate": _datefromstring,
    }
    func = routes.get(key, _callback)
    return func(value)
=======
""" streams-level utils """

from datetime import (
    timedelta,
    datetime,
    timezone,
)
from urllib.parse import urlparse
import os
import sys
import ctypes
import mutagen
import humanize
import exiftool

# system sleep inhibit/release constants
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

INHIBIT = ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED
RELEASE = ES_CONTINUOUS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def prevent_sleep():
    """ prevent the system from sleeping """
    try:
        # Windows
        ctypes.windll.kernel32.SetThreadExecutionState(INHIBIT)
    except Exception:
        pass


def allow_sleep():
    """ release the sleep lock """
    try:
        # Windows
        ctypes.windll.kernel32.SetThreadExecutionState(RELEASE)
    except Exception:
        pass


def r_path(relpath, base_dir=BASE_DIR) -> str:
    """ get absolute path, when running file or frozen """

    base_path = getattr(sys, "_MEIPASS", base_dir)
    abs_path = os.path.join(base_path, relpath)
    return abs_path if os.path.exists(abs_path) else base_dir


def is_url(url: str) -> bool:
    """ return if url is valid """
    try:
        result = urlparse(url.strip())
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def strfdelta(secs, fmt="{days}:{hours}:{minutes:02}:{seconds:02}") -> str:
    """ create timedelta from secs, string format timedelta """
    tdelta = timedelta(seconds=secs)
    d = {"days": tdelta.days}
    d["hours"], rem = divmod(tdelta.seconds, 3600)
    d["minutes"], d["seconds"] = divmod(rem, 60)
    return fmt.format(**d)


def fmt_seconds(secs) -> str:
    """ return formatted time as H:M:S """
    days, rem = divmod(round(secs), 86400)
    hours, rem = divmod(round(rem), 3600)
    minutes, seconds = divmod(round(rem), 60)

    fmt = ""
    if days:
        fmt = f"{days}d:"
    if hours:
        fmt = f"{fmt}{hours:02}:"
    if minutes:
        fmt = f"{fmt}{minutes:02}:"
    if seconds:
        fmt = f"{fmt}{round(seconds):02}"
    else:
        fmt = "00:00"
    return fmt


def from_exiftool(file: str, ex_path: str) -> dict:
    """ get metadata as dict using exiftool """
    try:
        with exiftool.ExifToolHelper(executable=ex_path, common_args=None, encoding="utf-8") as et:
            data = et.get_metadata(file)[0]
            channels = data.get("ChannelMode") or f'{data.get("AudioChannels")} channels'
            sr = data.get("OutputAudioSampleRate") or data.get("AudioSampleRate")

            try:
                cleaned = {
                    "duration": f'{data.get("Duration", " ")}'.split(" ")[0],
                    "mimetype": data.get("MIMEType"),
                    "audio": f'{channels}, {sr:,} Hz',
                    "permissions": data.get("FilePermissions"),
                    "resolution": data.get("ImageSize"),
                    "fps": data.get("VideoFrameRate"),
                }
            except Exception:
                cleaned = {
                    "mimetype": data.get("MIMEType"),
                    "audio": f"{channels}, {data.get('SampleRate')} Hz"
                }
            return cleaned

    except Exception:
        return {}


def file_details(filename, exiftool_path=None):
    """ get local file metadata """
    try:
        meta = None
        dt = datetime.fromtimestamp(os.path.getctime(filename), tz=timezone.utc)
        c_human = humanize.naturaltime(dt)
        try:
            file: mutagen.FileType = mutagen.File(filename)

            if file:  # is not None
                info = file.info
                cover = file.tags.getall("APIC")
                if cover:
                    thumb_data = cover[0].data
                else:
                    thumb_data = None
                meta = {
                    "thumbnail": thumb_data,  # data or None
                    "duration": fmt_seconds(info.length),
                    "audio": f"{info.channels} channels, {info.bitrate / 1000} kbps, {info.sample_rate:,} Hz",
                }
            else:
                meta = from_exiftool(filename, exiftool_path)
        except Exception:
            meta = from_exiftool(filename, exiftool_path)

        offline = {
            "path": os.path.dirname(filename),
            "type": f"{os.path.splitext(filename)[1].strip('.').upper()} File",
            "filesize": humanize.naturalsize(os.path.getsize(filename)),
            "created": f"{c_human} ({dt.strftime('%d %b %Y')})",
        }
        if meta:
            offline.update(meta)

        # if no external, get offline
        return offline

    except Exception:
        return {}


def safe_delete(filename: str):
    """ skip exceptions that may occur when deleting """
    try:
        os.remove(filename)
    except Exception:
        pass


def _datefromstring(date: str, fmt="%Y:%m:%d %H:%M:%S%z") -> str:
    """ parse datetime from string """
    dt = datetime.strptime(date, fmt)
    fmtd = f"{humanize.naturaltime(dt)} ({dt.strftime('%d %b %Y')})"
    return fmtd


def _callback(value: str) -> str:
    """ callaback function for dict routing """
    return value


def _format_values(key: str, value: str):
    routes = {
        "FileCreateDate": _datefromstring,
    }
    func = routes.get(key, _callback)
    return func(value)
>>>>>>> a4e48a141439482a4b6694fbb454ee0b61de7240
