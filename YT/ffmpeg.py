""" ffmpeg file download and conversion functions """

# option placement matters
# ffmpeg [global options] [input options] -i input [output options] output

import os
import re
from YT.utils import (
    r_path,
)


APP_DIR = os.path.dirname(r_path("YT"))  # this removes YT and returns app dir

DATA_DIR = os.path.join(APP_DIR, "data")

FFMPEG_DIR = os.path.join(APP_DIR, "ffmpeg")

FFMPEG_PATH = os.path.join(FFMPEG_DIR, "bin", "ffmpeg.exe")
FFPROBE_PATH = os.path.join(FFMPEG_DIR, "bin", "ffprobe.exe")


def callback_func(cmd):
    yield


def _make_cmd(info_dict: dict, stream: dict) -> list:
    """ create dynamic ffmpeg cmd from info_dict """
    common_cmd = []

    downloader_opts = stream.get('downloader_options')
    if downloader_opts:
        ffmpeg_args = downloader_opts.get('ffmpeg_args', [])
        common_cmd += ffmpeg_args

    seekable = info_dict.get('_seekable')
    if seekable is not None:
        # setting -seekable prevents ffmpeg from guessing if the server
        # supports seeking(by adding the header `Range: bytes=0-`), which
        # can cause problems in some cases
        # https://github.com/ytdl-org/youtube-dl/issues/11800#issuecomment-275037127
        # http://trac.ffmpeg.org/ticket/6125#comment:10
        common_cmd += ['-seekable', '1' if seekable else '0']

    # protocol
    protocol = info_dict.get('protocol')
    if protocol == 'rtmp':
        player_url = info_dict.get('player_url')
        page_url = info_dict.get('page_url')
        app = info_dict.get('app')
        play_path = info_dict.get('play_path')
        tc_url = info_dict.get('tc_url')
        flash_version = info_dict.get('flash_version')
        live = info_dict.get('rtmp_live', False)
        conn = info_dict.get('rtmp_conn')
        if player_url is not None:
            common_cmd += ['-rtmp_swfverify', player_url]
        if page_url is not None:
            common_cmd += ['-rtmp_pageurl', page_url]
        if app is not None:
            common_cmd += ['-rtmp_app', app]
        if play_path is not None:
            common_cmd += ['-rtmp_playpath', play_path]
        if tc_url is not None:
            common_cmd += ['-rtmp_tcurl', tc_url]
        if flash_version is not None:
            common_cmd += ['-rtmp_flashver', flash_version]
        if live:
            common_cmd += ['-rtmp_live', 'live']
        if isinstance(conn, list):
            for entry in conn:
                common_cmd += ['-rtmp_conn', entry]
        elif isinstance(conn, str):
            common_cmd += ['-rtmp_conn', conn]

    # starttime, stoptime
    start_time, end_time = info_dict.get('section_start') or 0, info_dict.get('section_end')
    if start_time:
        common_cmd += ['-ss', str(start_time)]
    if end_time:
        common_cmd += ['-t', str(end_time - start_time)]

    http_headers = stream.get("http_headers")
    if http_headers and re.match(r'^https?://', stream['url']):
        # Trailing \r\n after each HTTP header is important to prevent warning from ffmpeg/avconv:
        # [http @ 00000000003d2fa0] No trailing CRLF found in HTTP header.
        common_cmd.extend(['-headers', ''.join(f'{k}: {v}\r\n' for k, v in http_headers.items())])

    return common_cmd


def to_mp3(
    media_path,
    cover,
    fmt="mp3",
    output=None,
    preset=None,
    stream=None,
    info_dict=None,
    cmd_runner=None
):
    """ convert audio `media_path` format to `fmt` """
    cmd_runner = cmd_runner or callback_func

    opts_cmd = []
    if info_dict:
        opts_cmd = _make_cmd(info_dict, stream)

    if not output:  # when media_path is a file path
        name, ext = os.path.splitext(media_path)
        output = f"{name}.{fmt}"

    # ffmpeg [global options] [input options] -i input [output options] output
    cmd = [
        FFMPEG_PATH,
        "-y",  # overwrite output
        "-progress", "pipe:1",  # write to stdout
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_on_network_error", "1",
        "-reconnect_delay_max", "60",  # give up after this seconds
        "-reconnect_on_http_error", "1",
        # "-cpu-used", "0",
        # "-threads", "2",
        "-i", media_path,
        "-i", cover,
        # "-v", "error",
        "-map", "0:0",
        "-map", "1:0",
        "-id3v2_version", "3",
        "-metadata:s:v", "title='Album cover'",
        "-metadata:s:v", "comment='Cover (front)'",
        "-preset", preset or "medium",
    ]
    cmd.extend(opts_cmd)
    cmd.append(output)

    yield from cmd_runner(cmd)


def add_audio(
    video,
    audio,
    output,
    preset=None,
    stream=None,
    info_dict=None,
    cmd_runner=None
):
    """ add audio to video (not mixing) """
    cmd_runner = cmd_runner or callback_func

    opts_cmd = []
    if info_dict:
        opts_cmd = _make_cmd(info_dict, stream)

    # ffmpeg [global options] [input options] -i input [output options] output
    cmd = [
        FFMPEG_PATH,
        "-y",  # overwrite if output exists
        "-progress", "pipe:1",  # write to stdout
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_on_network_error", "1",
        "-reconnect_delay_max", "60",  # give up after this seconds
        "-reconnect_on_http_error", "1",
        "-i", video, "-i", audio,
        # "-v", "error",  # log errors, we're interested in them
        "-map", "0:v:0",  # grab video only (track 0) from index 0 (video input)
        "-map", "1:a:0",  # grab track 0 from index 1 (audio input)
        "-c:v", "copy",  # copy video data, no re-encoding
        # "-c:a", "aac",  # use aac codec for audio
        "-preset", preset or "medium",
    ]
    cmd.extend(opts_cmd)
    cmd.append(output)

    yield from cmd_runner(cmd)


def to_mp4(
    video,
    output,
    preset=None,
    stream=None,
    info_dict=None,
    cmd_runner=None
):
    """ video to mp4 """
    cmd_runner = cmd_runner or callback_func

    opts_cmd = []
    if info_dict:
        opts_cmd = _make_cmd(info_dict, stream)

    name, ext = os.path.splitext(video)
    if ext != ".mp4":
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-progress", "pipe:1",  # write to stdout
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_on_network_error", "1",
            "-reconnect_delay_max", "60",  # give up after this seconds
            "-reconnect_on_http_error", "1",
            "-i", video,
            "-c:v", "copy",
            "-preset", preset or "medium",
        ]
        cmd.extend(opts_cmd)
        cmd.append(output)

        yield from cmd_runner(cmd)


def ffmpeg_dash_download(
    video_link,
    audio_link,
    output,
    preset=None,
    func=None,
    stream=None,
    info_dict=None
):
    yield from add_audio(
        video_link,
        audio_link,
        output,
        preset=preset,
        stream=stream,
        info_dict=info_dict,
        cmd_runner=func
    )


def ffmpeg_video_download(
    video_link,
    output,
    preset=None,
    func=None,
    stream=None,
    info_dict=None
):
    yield from to_mp4(
        video_link,
        output,
        preset=preset,
        info_dict=info_dict,
        stream=stream,
        cmd_runner=func
    )


def ffmpeg_audio_download(
    audio_link,
    cover_link,
    output,
    preset=None,
    func=None,
    stream=None,
    info_dict=None
):
    yield from to_mp3(
        audio_link,
        cover_link,
        output=output,
        info_dict=info_dict,
        stream=stream,
        preset=preset,
        cmd_runner=func
    )
