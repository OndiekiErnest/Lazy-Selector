__author__ = "Ernesto"
__email__ = "ernestondieki12@gmail.com"

# option placement matters
# ffmpeg [global options] [input options] -i input [output options] output

from subprocess import run, STARTUPINFO, STARTF_USESHOWWINDOW
from os.path import join, abspath, dirname, exists, splitext
from os import remove, mkdir
import sys


BASE_DIR = dirname(abspath(__file__))


def r_path(relpath):
    """
        Get absolute path
    """

    base_path = getattr(sys, "_MEIPASS", BASE_DIR)
    return join(base_path, relpath)


YT_DIR = r_path("YT")
YT_DIR = YT_DIR if exists(YT_DIR) else BASE_DIR  # else is true when running Lazy_Selector as a file, not app

DATA_DIR = join(YT_DIR, "data")

FFMPEG_DIR = join(YT_DIR, "ffmpeg")

# PATH = join(FFMPEG_DIR, "bin", "ffmpeg.exe")  # uncomment this if you have ffmpeg.exe put in bin folder
PATH = "ffmpeg"  # if you have ffmpeg path set on environment variables

FFMPEG_OUT_FILE = join(DATA_DIR, "ffmpeg_errors.txt")

NO_WIN = STARTUPINFO()
NO_WIN.dwFlags |= STARTF_USESHOWWINDOW


def safe_delete(filename: str):
    """ skip exceptions that may occur when deleting """
    try:
        remove(filename)
    except Exception:
        pass


def ffmpeg_process(cmd: list):
    """ blocking function; run cmd using subprocess """

    try:
        # over-write with the most recent errors
        with open(FFMPEG_OUT_FILE, "wb") as error_file:

            run(cmd,
                stderr=error_file,
                check=True,
                startupinfo=NO_WIN,
                )
    except FileNotFoundError:
        mkdir(DATA_DIR)
        ffmpeg_process(cmd)


def to_mp3(filename, cover, fmt="mp3", preset=None):
    """ convert audio `filename` format to `fmt` """
    name, ext = splitext(filename)

    if ext.strip(".") != fmt:
        output = f"{name}.{fmt}"
        # ffmpeg [global options] [input options] -i input [output options] output
        cmd = [
            PATH,
            "-y",  # overwrite output
            # "-cpu-used", "0",
            "-threads", "2",
            "-i", filename,
            "-i", cover,
            "-v", "error",
            "-map", "0:0",
            "-map", "1:0",
            "-id3v2_version", "3",
            "-metadata:s:v", "title='Album cover'",
            "-metadata:s:v", "comment='Cover (front)'",
            "-preset", preset or "medium",
            output,
        ]

        ffmpeg_process(cmd)


def add_audio(video, audio, output, remove_src=False, preset=None):
    """ add audio to video (not mixing) """

    # ffmpeg [global options] [input options] -i input [output options] output
    cmd = [
        PATH,
        "-y",  # overwrite if output exists
        "-i", video, "-i", audio,
        "-v", "error",  # log errors, we're interested in them
        "-map", "0:v:0",  # grab video only (track 0) from index 0 (video input)
        "-map", "1:a:0",  # grab track 0 from index 1 (audio input)
        "-c:v", "copy",  # copy video data, no re-encoding
        "-c:a", "aac",  # use aac codec for audio
        "-preset", preset or "medium",
        output,
    ]

    ffmpeg_process(cmd)

    if remove_src:
        safe_delete(audio)
        safe_delete(video)


def reduce_vid_size(filename):
    """ use crf, slower preset for small file size mp4 vids """
    name, ext = splitext(filename)

    # ffmpeg [global options] [input options] -i input [output options] output
    cmd = [
        PATH,
        "-i", filename,
        "-vcodec", "libx265",
        "-crf", "28",
        "-preset", "slower",
        f"{name}_c{ext}"
    ]

    ffmpeg_process(cmd)


def ffmpeg_video_download(video, audio, output):
    """ download youtube vids using stream links """
    # ffmpeg -i "YOUR URL TO DOWNLOAD VIDEO FROM" -c:v libx264 -preset slow -crf 22 "saveas.mp4"
    # hw
    # ffmpeg -i "URL" -preset medium -c:v hevc_nvenc -rc constqp -qp 31 -c:a aac -b:a 64k -ac 1 “name_output.mp4”
