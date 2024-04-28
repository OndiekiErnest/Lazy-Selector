<<<<<<< HEAD
""" youtube functionalities """

from collections import namedtuple
from datetime import (
    datetime,
)
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
    size = (item.get("filesize", 0) or 0) or (item.get("vbr", 0) or 0)
    return (width, -size)  # negate size, to sort in opposite order


def _video_presentation(item: dict) -> str:
    """ return presentation str for item """
    if user_agent := item.get("http_headers", {}).get("User-Agent"):
        if user_agent.startswith("facebookexternalhit"):
            return f"{item.get('width')}p ({round(item.get('vbr', 0))} VBR)"

    res = item.get("format_note")
    return f"{item.get('format')} {RES_MAP.get(res, '')}"


def _is_validvid(item: dict):
    """ return true if stream is valid video """
    width = item.get("width")
    f = item.get("format_note")
    container = item.get("container")
    is_hls = item.get("format_id", "None").startswith("hls")
    yt_valid = (width and container and (f in VID_FILTER))
    fb_vid = (item.get("format_note") == "DASH video")
    return yt_valid or is_hls or fb_vid


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

    try:
        title = normalize_filename(sinfo.get("title", ""))
        audio_stream = get_best_audio(sinfo)  # get the best audio stream or None
        duration = sinfo.get("duration", 0)

        vid_streams = _filter_vids(sinfo.get("formats"))

        for item in vid_streams:

            url = item.get("url")
            filesize = item.get("filesize", 0) or 0
            p_size = humanize.naturalsize(filesize) if filesize else ""
            p = _video_presentation(item)  # presentation

            yield VideoStream(
                url,
                title,
                audio_stream,
                duration,
                p_size,
                p,
                item,
            )

    except Exception:
        yield


def get_play_stream(sinfo: dict):
    """ return audio for streaming, if None, return video stream """
    aud = get_best_audio(sinfo)
    if aud:
        return aud
    return next(get_video_streams(sinfo))  # get video stream if no audio stream


def get_sanitizedinfo(url: str) -> dict:
    """ extract and get yt sanitized info from url """
    try:
        with yt_dlp.YoutubeDL() as yt:
            info = yt.extract_info(url, download=False)
            return yt.sanitize_info(info)
    except Exception:
        return {}
=======
""" youtube functionalities """

from collections import namedtuple
from datetime import (
    datetime,
)
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

    except Exception:
        yield


def get_play_stream(sinfo: dict):
    """ return audio for streaming, if None, return video stream """
    aud = get_best_audio(sinfo)
    if aud:
        return aud
    return next(get_video_streams(sinfo))  # get video stream if no audio stream


def get_sanitizedinfo(url: str) -> dict:
    """ extract and get yt sanitized info from url """
    try:
        with yt_dlp.YoutubeDL() as yt:
            info = yt.extract_info(url, download=False)
            return yt.sanitize_info(info)
    except Exception:
        return {}
>>>>>>> a4e48a141439482a4b6694fbb454ee0b61de7240
