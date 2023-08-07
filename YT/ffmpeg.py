""" ffmpeg file download and conversion functions """

# option placement matters
# ffmpeg [global options] [input options] -i input [output options] output

import os
from YT.utils import (
    r_path,
)


APP_DIR = os.path.dirname(r_path("YT"))  # this removes YT and returns app dir

DATA_DIR = os.path.join(APP_DIR, "data")

FFMPEG_DIR = os.path.join(APP_DIR, "ffmpeg")

PATH = os.path.join(FFMPEG_DIR, "bin", "ffmpeg.exe")


def callback_func(cmd):
    yield


def to_mp3(media_path, cover, fmt="mp3", output=None, preset=None, cmd_runner=None):
    """ convert audio `media_path` format to `fmt` """
    cmd_runner = cmd_runner or callback_func

    if not output:  # when media_path is a file path
        name, ext = os.path.splitext(media_path)
        output = f"{name}.{fmt}"

    # ffmpeg [global options] [input options] -i input [output options] output
    cmd = [
        PATH,
        "-y",  # overwrite output
        "-progress", "pipe:1",  # write to stdout
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_on_network_error", "1",
        "-reconnect_delay_max", "60",  # give up after this seconds
        "-reconnect_on_http_error", "1",
        # "-cpu-used", "0",
        "-threads", "2",
        "-i", media_path,
        "-i", cover,
        # "-v", "error",
        "-map", "0:0",
        "-map", "1:0",
        "-id3v2_version", "3",
        "-metadata:s:v", "title='Album cover'",
        "-metadata:s:v", "comment='Cover (front)'",
        "-preset", preset or "medium",
        output,
    ]

    yield from cmd_runner(cmd)


def add_audio(video, audio, output, preset=None, cmd_runner=None):
    """ add audio to video (not mixing) """
    cmd_runner = cmd_runner or callback_func

    # ffmpeg [global options] [input options] -i input [output options] output
    cmd = [
        PATH,
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
        # commented out because it cuts audio few seconds to the end of video
        "-c:a", "aac",  # use aac codec for audio
        "-preset", preset or "medium",
        output,
    ]

    yield from cmd_runner(cmd)


def to_mp4(video, output, preset=None, cmd_runner=None):
    """ video to mp4 """
    cmd_runner = cmd_runner or callback_func

    name, ext = os.path.splitext(video)
    if ext != ".mp4":
        cmd = [
            PATH,
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
            output,
        ]
        yield from cmd_runner(cmd)


def ffmpeg_dash_download(video_link, audio_link, output, preset=None, func=None):
    print(video_link, audio_link)
    yield from add_audio(video_link, audio_link, output, preset=preset, cmd_runner=func)


def ffmpeg_video_download(video_link, output, preset=None, func=None):
    yield from to_mp4(video_link, output, preset=preset, cmd_runner=func)


def ffmpeg_audio_download(audio_link, cover_link, output, preset=None, func=None):
    yield from to_mp3(audio_link, cover_link, output=output, preset=preset, cmd_runner=func)
