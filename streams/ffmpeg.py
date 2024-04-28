<<<<<<< HEAD
""" ffmpeg functions """

import os
from streams.utils import (
    r_path,
)


APP_DIR = os.path.dirname(r_path("YT"))  # this removes YT and returns app dir

DATA_DIR = os.path.join(APP_DIR, "data")

FFMPEG_DIR = os.path.join(APP_DIR, "ffmpeg")

FFMPEG_PATH = os.path.join(FFMPEG_DIR, "bin", "ffmpeg.exe")


def list_cmd(cmd):
    """ just print cmd """
    print(f"Your command:\n{cmd}")


def to_mp3(
    media_path,
    cover,
    fmt="mp3",
    output=None,
    preset=None,
    ffkwargs=None,
    cmd_runner=None,
):
    """ convert audio `media_path` format to `fmt` """
    cmd_runner = cmd_runner or list_cmd

    if not output:  # when media_path is a file path
        name, ext = os.path.splitext(media_path)
        output = f"{name}.{fmt}"

    # ffmpeg [global options] [input options] -i input [output options] output
    cmd = [
        FFMPEG_PATH,
        "-y",  # overwrite output
        "-progress", "pipe:1",  # write to stdout
        # "-cpu-used", "0",
        "-threads", "16",
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
    if ffkwargs:
        cmd.extend(ffkwargs)
    cmd.append(output)

    cmd_runner(cmd)


def add_audio(
    video,
    audio,
    output,
    preset=None,
    cmd_runner=None,
):
    """ add audio to video (not mixing) """
    cmd_runner = cmd_runner or list_cmd

    # ffmpeg [global options] [input options] -i input [output options] output
    cmd = [
        FFMPEG_PATH,
        "-y",  # overwrite if output exists
        "-progress", "pipe:1",  # write to stdout
        "-i", video, "-i", audio,
        # "-v", "error",
        "-map", "0:v:0",  # grab video only (track 0) from index 0 (video input)
        "-map", "1:a:0",  # grab track 0 from index 1 (audio input)
        "-c:v", "copy",  # copy video data, no re-encoding
        "-c:a", "aac",  # use aac codec for audio
        "-preset", preset or "medium",
        output,
    ]

    cmd_runner(cmd)


def to_mp4(
    video,
    output,
    preset=None,
    cmd_runner=None,
):
    """ video to mp4 """
    cmd_runner = cmd_runner or list_cmd

    if os.path.isfile(video):
        name, ext = os.path.splitext(video)
        if ext != ".mp4":
            cmd = [
                FFMPEG_PATH,
                "-y",
                "-progress", "pipe:1",  # write to stdout
                "-i", video,
                "-c:v", "copy",
                "-preset", preset or "medium",
                output,
            ]

            cmd_runner(cmd)
    else:
        # link
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-progress", "pipe:1",  # write to stdout
            "-i", video,
            "-codec", "copy",
            "-preset", preset or "medium",
            output,
        ]

        cmd_runner(cmd)
=======
""" ffmpeg functions """

import os
from streams.utils import (
    r_path,
)


APP_DIR = os.path.dirname(r_path("YT"))  # this removes YT and returns app dir

DATA_DIR = os.path.join(APP_DIR, "data")

FFMPEG_DIR = os.path.join(APP_DIR, "ffmpeg")

FFMPEG_PATH = os.path.join(FFMPEG_DIR, "bin", "ffmpeg.exe")


def list_cmd(cmd):
    """ just print cmd """
    print(f"Your command:\n{cmd}")


def to_mp3(
    media_path,
    cover,
    fmt="mp3",
    output=None,
    preset=None,
    ffkwargs=None,
    cmd_runner=None,
):
    """ convert audio `media_path` format to `fmt` """
    cmd_runner = cmd_runner or list_cmd

    if not output:  # when media_path is a file path
        name, ext = os.path.splitext(media_path)
        output = f"{name}.{fmt}"

    # ffmpeg [global options] [input options] -i input [output options] output
    cmd = [
        FFMPEG_PATH,
        "-y",  # overwrite output
        "-progress", "pipe:1",  # write to stdout
        # "-cpu-used", "0",
        "-threads", "16",
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
    if ffkwargs:
        cmd.extend(ffkwargs)
    cmd.append(output)

    cmd_runner(cmd)


def add_audio(
    video,
    audio,
    output,
    preset=None,
    cmd_runner=None,
):
    """ add audio to video (not mixing) """
    cmd_runner = cmd_runner or list_cmd

    # ffmpeg [global options] [input options] -i input [output options] output
    cmd = [
        FFMPEG_PATH,
        "-y",  # overwrite if output exists
        "-progress", "pipe:1",  # write to stdout
        "-i", video, "-i", audio,
        # "-v", "error",
        "-map", "0:v:0",  # grab video only (track 0) from index 0 (video input)
        "-map", "1:a:0",  # grab track 0 from index 1 (audio input)
        "-c:v", "copy",  # copy video data, no re-encoding
        "-c:a", "aac",  # use aac codec for audio
        "-preset", preset or "medium",
        output,
    ]

    cmd_runner(cmd)


def to_mp4(
    video,
    output,
    preset=None,
    cmd_runner=None,
):
    """ video to mp4 """
    cmd_runner = cmd_runner or list_cmd

    if os.path.isfile(video):
        name, ext = os.path.splitext(video)
        if ext != ".mp4":
            cmd = [
                FFMPEG_PATH,
                "-y",
                "-progress", "pipe:1",  # write to stdout
                "-i", video,
                "-c:v", "copy",
                "-preset", preset or "medium",
                output,
            ]

            cmd_runner(cmd)
    else:
        # link
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-progress", "pipe:1",  # write to stdout
            "-i", video,
            "-codec", "copy",
            "-preset", preset or "medium",
            output,
        ]

        cmd_runner(cmd)
>>>>>>> a4e48a141439482a4b6694fbb454ee0b61de7240
