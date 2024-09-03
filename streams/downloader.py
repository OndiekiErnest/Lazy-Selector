""" aria downloader functions and classes """


import os
import aria2p
import humanize
import logging
import subprocess
from streams.utils import (
    r_path,
    safe_delete,
)
from threading import (
    Thread, Lock
)
from time import sleep
from datetime import (
    timedelta,
)
from ffmpeg_progress_yield import (
    FfmpegProgress,
)
from concurrent.futures import (
    ThreadPoolExecutor,
)
from streams.ffmpeg import (
    to_mp3,
    to_mp4,
    add_audio,
)
from multiprocessing import (
    Process,
)
from multiprocessing.managers import (
    SyncManager,
)
from collections import namedtuple
from typing import (
    Optional,
)

NO_WIN = subprocess.STARTUPINFO()
NO_WIN.dwFlags |= subprocess.STARTF_USESHOWWINDOW

APP_DIR = os.path.dirname(r_path("YT"))
# aria
ARIA_DIR = os.path.join(APP_DIR, "aria2")
ARIA_PATH = os.path.join(ARIA_DIR, "aria2c.exe")
# server
ARIA_SECRET = "@LaZy?"
ARIA_HOST = "http://localhost"
ARIA_PORT = 6800
# process-task
Task = namedtuple("Task", ["funcname", "args", "kwargs"])

logger = logging.getLogger(__name__)


def fmt_delta(delta: timedelta) -> str:
    """ return formatted timedelta """
    secs = delta.total_seconds()
    days, rem = divmod(round(secs), 86400)
    hours, rem = divmod(round(rem), 3600)
    minutes, seconds = divmod(round(rem), 60)
    seconds = round(seconds)

    if days:
        return "0d" if days == 1000000000 else f"{days}d{hours}h{minutes}m{seconds}s"
    elif hours:
        return f"{hours}h{minutes}m{seconds}s"
    elif minutes:
        return f"{minutes}m{seconds}s"
    elif seconds:
        return f"{seconds}s"
    else:
        return "0s"


def start_aria2(parent_pid: str) -> Optional[subprocess.Popen]:
    """
    start aria2 daemon process that exits
    when parent with `parent_pid` exits
    return True on successful start
    """

    cmd = [
        ARIA_PATH,
        "--daemon=true",
        "--continue=true",
        "--http-accept-gzip=true",
        "--console-log-level=error",
        "--download-result=hide",
        "--no-conf",
        "-x16",
        "-j16",
        "-s16",
        "--min-split-size=1M",
        f"--stop-with-process={parent_pid}",
        "--enable-rpc=true",
        f"--rpc-secret={ARIA_SECRET}",
        "--allow-overwrite=true",
        "--auto-file-renaming=false",
    ]

    try:
        process = subprocess.Popen(
            cmd,
            startupinfo=NO_WIN,
        )
        return process
    except Exception as e:
        logger.exception(e)
        return


class PostConvertor():
    """
    file convertor using ffmpeg
    starts multiple instances of ffmpeg
    """
    __slots__ = (
        "max_threads",
        "active_convs",
        "total_progress",
        "avg_progress",
        "thread_lock",
        "thread_pool",
        "ffprocess",
        "conv_error",
    )

    def __init__(self, max_threads=1):

        self.max_threads = max_threads
        self.active_convs = 0
        self.total_progress = 0
        self.avg_progress = 0
        self.conv_error = 0

    def start_threadpool(self):
        """ create threadpool """
        thread_pool = getattr(self, "thread_pool", None)
        if not thread_pool:
            self.thread_lock = Lock()
            # process pool executor
            self.thread_pool = ThreadPoolExecutor(
                max_workers=self.max_threads,
                thread_name_prefix="Conv_",
            )

    def onDoneConv(self, files):
        """ pass files to be deleted when future is done """

        def delete_src(*args):  # receives a Future obj
            """ delete files """
            for file in files:
                if os.path.isfile(file):
                    safe_delete(file)
            # reduce active_convs number
            with self.thread_lock:
                self.active_convs -= 1
                if self.active_convs > 0:
                    self.total_progress -= 100
                else:
                    self.total_progress = 0

        return delete_src

    def _ffmpeg_with_progress(self, cmd):
        """ run ffmpeg, get the progress """

        try:
            self.ffprocess = FfmpegProgress(cmd)
            for progress in self.ffprocess.run_command_with_progress(
                popen_kwargs={'startupinfo': NO_WIN}
            ):
                self.total_progress = progress
        except Exception as e:
            logger.exception(e)
            self.conv_error += 1

    def convprogress(self) -> tuple:
        """ get average progress """

        return (self.total_progress, self.active_convs, self.conv_error)

    def enqueue_audio(
        self,
        media_path,
        cover,
        output=None,
        ffkwargs=None,
        preset=None,
    ):
        """ add to_mp3 process to queue """

        self.start_threadpool()

        self.active_convs += 1
        future = self.thread_pool.submit(
            to_mp3,
            media_path,
            cover,
            output=output,
            ffkwargs=ffkwargs,
            preset=preset,
            cmd_runner=self._ffmpeg_with_progress,
        )
        future.add_done_callback(self.onDoneConv((media_path, )))

    def enqueue_video(
        self,
        video,
        output,
        preset=None,
    ):
        """ add to_mp4 process to queue """
        self.start_threadpool()

        self.active_convs += 1
        future = self.thread_pool.submit(
            to_mp4,
            video,
            output,
            preset=preset,
            cmd_runner=self._ffmpeg_with_progress,
        )
        future.add_done_callback(self.onDoneConv((video, )))

    def enqueue_dash(
        self,
        video,
        audio,
        output,
        preset=None,
    ):
        """ add dash process to queue """
        self.start_threadpool()

        self.active_convs += 1
        future = self.thread_pool.submit(
            add_audio,
            video,
            audio,
            output,
            preset=preset,
            cmd_runner=self._ffmpeg_with_progress,
        )
        future.add_done_callback(self.onDoneConv((video, audio)))

    def close(self):
        """
        quit when futures are done
        """
        ffprocess = getattr(self, "ffprocess", None)
        if ffprocess:
            try:
                ffprocess.quit_gracefully()
            except RuntimeError:
                pass
        try:
            self.thread_pool.shutdown(wait=False, cancel_futures=True)
        except AttributeError:
            pass


class BaseDownloader(Process):
    """
    base downloader class
    subclass: Process
    """
    __slots__ = (
        "shared_dict",
        "process_running",
    )

    def __init__(
        self, shared_dict: SyncManager.dict,
        *args, daemon=True, **kwargs
    ):
        super().__init__(*args, daemon=daemon, name="Lazy_Downloader", **kwargs)
        self.shared_dict = shared_dict
        self.process_running = False

    def dispatch(self, msg: Task):
        funcname, args, kwargs = msg

        handler = getattr(self, funcname, None)
        if handler:
            rtv = handler(*args, **kwargs)
            self.shared_dict[handler.__name__] = rtv
        else:
            self.shared_dict[funcname] = None

    def run(self):
        self.process_running = True
        get_task = self.shared_dict.pop

        while self.process_running:
            msg = get_task("task", None)
            if msg:
                self.dispatch(msg)
            sleep(1)
        self.process_running = False


class ADownloader(BaseDownloader):
    """
    Aria2-based file downloader
    bases BaseDownloader
    """
    __slots__ = (
        "file_convertor", "aria_client",
        "parent_pid", "prog_monitor_running",
        "active_downloads", "aria_process",
        "progress_monitor_thread",
        "errored_num", "prog_thread_running",
    )

    def __init__(
        self, parent_pid,
        shared_dict: SyncManager.dict,
        *args, **kwargs
    ):
        # instantiate parent class
        super().__init__(shared_dict, *args, **kwargs)

        # post processor
        self.file_convertor = PostConvertor()

        # attrs
        self.parent_pid = parent_pid
        self.active_downloads = {}
        self.prog_monitor_running = False
        self.prog_thread_running = False
        self.errored_num = 0

    def _to_display(self, txt: str):
        try:
            self.shared_dict["progress"] = txt
        except Exception:
            pass

    def is_done(self) -> bool:
        """ return True if all done downloading """
        # return all((d.is_complete for d in self.get_downloads()))  # this is slow
        return len(self.active_downloads) == 0

    def start_ariaAPI(self):
        """ start api if not started yet """
        a_api = getattr(self, "aria_client", None)
        if not a_api:
            # start aria process first for the client to connect to
            self.aria_process = start_aria2(self.parent_pid)
            # start aria client
            client = aria2p.Client(
                host=ARIA_HOST,
                port=ARIA_PORT,
                secret=ARIA_SECRET
            )
            self.aria_client = aria2p.API(client)
            # listen to aria2 events
            self.aria_client.listen_to_notifications(
                threaded=True,
                on_download_complete=self._download_complete,
                on_download_error=self._download_error,
            )
        else:
            if self.aria_process.poll():
                # restart aria process first for the client to connect to
                delattr(self, "aria_client")
                self.start_ariaAPI()

    def _monitor_progress(self):
        """ consolidate progress, update user """
        self.prog_monitor_running = True
        get_downloads = self.aria_client.get_downloads
        get_size = humanize.naturalsize
        f_delta = fmt_delta
        avg_convprogress = self.file_convertor.convprogress
        last_error = "n03rr0r"

        while self.prog_monitor_running:
            # sleep
            sleep(0.7)

            c_p, acv, conv_error = avg_convprogress()
            cnv_err = f", Failed conversions: {conv_error}" if conv_error else ""
            conv_str = f"\nFFMPEG Converting... {c_p}% ({max(acv - 1, 0)} waiting)" if acv else ""
            err_str = f"\nFailed downloads: {self.errored_num}{cnv_err}" if self.errored_num else ""
            if self.active_downloads:

                try:
                    active_downloads = get_downloads()
                    # calculate speed and eta
                    # (downloaded, total, speed, eta)
                    download_dets = (
                        (
                            d.completed_length,
                            d.total_length,
                            d.download_speed,
                            d.eta
                        ) for d in active_downloads if d.is_active
                    )
                    # initialize values
                    downloaded, total_size, speed = 0, 0, 0
                    etarr = timedelta(0)
                    active_d_len = 0
                    # get sum
                    for d, t, s, e in download_dets:
                        downloaded += d
                        total_size += t
                        speed += s
                        etarr += e
                        active_d_len += 1
                    # get average from sum
                    downloaded = get_size(downloaded)
                    total_size = get_size(total_size)
                    speed = get_size((speed / active_d_len))
                    eta = f_delta((etarr / active_d_len))
                    # display
                    dsp_txt = (
                        f"({active_d_len}) {downloaded} / {total_size} ({speed}/s, {eta}){conv_str}{err_str}"
                    )
                    self._to_display(dsp_txt)

                except Exception as e:
                    logger.exception(e)
                    dsp_txt = f"{active_d_len} Downloading...{conv_str}{err_str}"
                    self._to_display(dsp_txt)
            else:
                if conv_str:
                    conv_str = conv_str.strip('\n')
                    dsp_txt = f"{conv_str}{err_str}"
                    self._to_display(dsp_txt)

                elif last_error == err_str:
                    break

                elif err_str:
                    err_str = err_str.strip('\n')
                    self._to_display(err_str)
                    last_error = err_str

                else:
                    dsp_txt = f"Converted successfully...{err_str}"
                    self._to_display(dsp_txt)
                    break
                # additional sleep
                sleep(0.7)
        self.prog_thread_running = False
        self.file_convertor.conv_error = 0
        self.errored_num = 0
        self.prog_monitor_running = False

    def start_monitoring_progress(self):
        """
        start thread to monitor progress
        stop loop as soon as downloads are done
        """
        if not self.prog_thread_running:

            self.progress_monitor_thread = Thread(
                target=self._monitor_progress,
                name="progress_m",
                daemon=True,
            )
            # start monitor thread
            self.progress_monitor_thread.start()
            self.prog_thread_running = True

    def video_download(self, stream, dst_path: str, *args, **kwargs):
        """ download video """

        # start api if not started
        self.start_ariaAPI()
        vid_ext = stream.info.get("video_ext")
        vidfilename = f"_{stream.title}_.{vid_ext}"
        vidopts = {
            "dir": dst_path,
            "out": vidfilename,
            "header": stream.info.get("http_headers"),
        }

        if stream.audio:
            aud_ext = stream.audio.info.get("audio_ext")
            audfilename = f"audio_{stream.title}_.{aud_ext}"

            audopts = {
                "dir": dst_path,
                "out": audfilename,
                "header": stream.info.get("http_headers"),
            }
            vid_d_obj = self.aria_client.add(stream.url, options=vidopts)[0]  # video
            aud_d_obj = self.aria_client.add(stream.audio.url, options=audopts)[0]  # audio
            # keep track
            self.active_downloads[vid_d_obj.gid] = {
                "video": vid_d_obj.gid,
                "audio": aud_d_obj.gid,
                "ext": aud_ext,
                "final_ext": "mp4",
                "thumbnail": None,
                "ffmpeg_preset": kwargs.get("preset"),
            }
            # to avoid getting None on `active_downloads.pop`
            self.active_downloads[aud_d_obj.gid] = {
                "video": vid_d_obj.gid,
                "audio": aud_d_obj.gid,
                "ext": aud_ext,
                "final_ext": "mp4",
                "thumbnail": None,
                "ffmpeg_preset": kwargs.get("preset"),
            }

        else:
            d_url = stream.url
            if d_url.endswith(".m3u8") or (vid_ext == "mp4"):
                # ffmpeg -i "http://example.com/chunklist.m3u8" -codec copy file.mp4
                vidfilename = f"{stream.title}.{vid_ext}"
                output = os.path.join(dst_path, vidfilename)
                self.file_convertor.enqueue_video(
                    d_url,
                    output,
                    preset=kwargs.get("preset"),
                )
            else:
                vid_d_obj = self.aria_client.add(d_url, vidopts)[0]
                # keep record
                self.active_downloads[vid_d_obj.gid] = {
                    "video": vid_d_obj.gid,
                    "audio": None,
                    "ext": vid_ext,
                    "final_ext": "mp4",
                    "thumbnail": None,
                    "ffmpeg_preset": kwargs.get("preset"),
                }
        # start monitor loop if not started
        self.start_monitoring_progress()

    def audio_download(self, stream, dst_path: str, *args, **kwargs):
        """ download audio """
        self.start_ariaAPI()
        aud_ext = stream.info.get("audio_ext")
        filename = f"_{stream.title}_.{aud_ext}"

        opts = {
            "dir": dst_path,
            "out": filename,
            "header": stream.info.get("http_headers"),
        }
        d_obj = self.aria_client.add(stream.url, options=opts)[0]
        # keep record
        self.active_downloads[d_obj.gid] = {
            "video": None,
            "audio": d_obj.gid,
            "ext": aud_ext,
            "final_ext": "mp3",
            "thumbnail": stream.thumbnail,
            "ffmpeg_preset": kwargs.get("preset"),
        }
        # start monitor loop if not started
        self.start_monitoring_progress()

    def _on_error(self, gid: str) -> tuple:
        """
        get relevant details when error occurs
        returns:
            name, dir, error_msg
        """
        d_dict = self.active_downloads.pop(gid, None)
        vid_d_gid = d_dict["video"]
        aud_d_gid = d_dict["audio"]

        if vid_d_gid and aud_d_gid:
            vid_d_obj, aud_d_obj = (
                self.aria_client.get_download(vid_d_gid),
                self.aria_client.get_download(aud_d_gid)
            )
            name = (
                vid_d_obj.name,
                aud_d_obj.name
            )
            folder = vid_d_obj.dir
            error_msg = vid_d_obj.error_message or aud_d_obj.error_message

            if vid_d_obj.has_failed:
                self.aria_client.remove([vid_d_obj])
                self.cancel_download(aud_d_obj)

            elif aud_d_obj.has_failed:
                self.aria_client.remove([aud_d_obj])
                self.cancel_download(vid_d_obj)

        elif vid_d_gid:
            vid_d_obj = self.aria_client.get_download(vid_d_gid)
            name = vid_d_obj.name
            folder = vid_d_obj.dir
            error_msg = vid_d_obj.error_message
            # remove record
            self.aria_client.remove([vid_d_obj])

        elif aud_d_gid:
            aud_d_obj = self.aria_client.get_download(aud_d_gid)
            name = aud_d_obj.name
            folder = aud_d_obj.dir
            error_msg = aud_d_obj.error_message
            # remove record
            self.aria_client.remove([aud_d_obj])
        else:
            name, folder, error_msg = None, None, None

        return name, folder, error_msg

    def _on_complete(self, gid: str) -> tuple:
        """
        get relevant details on done
        returns:
            name, dir
        """
        d_dict = self.active_downloads.pop(gid, None)
        vid_d_gid = d_dict["video"]
        aud_d_gid = d_dict["audio"]
        final_ext = d_dict["final_ext"]
        ext = d_dict["ext"]
        thumbnail = d_dict["thumbnail"]
        f_preset = d_dict["ffmpeg_preset"]

        if vid_d_gid and aud_d_gid:
            vid_d_obj = self.aria_client.get_download(vid_d_gid)
            aud_d_obj = self.aria_client.get_download(aud_d_gid)
            both_done = (vid_d_obj.is_complete and aud_d_obj.is_complete)
            if both_done:
                name = {
                    "video": vid_d_obj.name,
                    "audio": aud_d_obj.name,
                    "done": both_done,
                }
                folder = vid_d_obj.dir

            else:
                name, folder = None, None
        elif vid_d_gid:
            vid_d_obj = self.aria_client.get_download(vid_d_gid)
            name = vid_d_obj.name
            folder = vid_d_obj.dir

        elif aud_d_gid:
            aud_d_obj = self.aria_client.get_download(aud_d_gid)
            name = aud_d_obj.name
            folder = aud_d_obj.dir
        else:
            name, folder = None, None

        return folder, name, ext, final_ext, thumbnail, f_preset

    def _download_complete(self, api, gid: str):
        """ callback for complete done event """
        folder, name, ext, final_ext, thumbnail, f_p = self._on_complete(gid)
        if isinstance(name, dict):
            # dash video
            if name["done"]:  # all to finished

                vidname, audname = (
                    folder.joinpath(name["video"]),
                    folder.joinpath(name["audio"])
                )
                stem, _ = os.path.splitext(name["video"])
                output = folder.joinpath(f"{stem.strip('_')}.{final_ext}")
                self.file_convertor.enqueue_dash(
                    str(vidname),
                    str(audname),
                    str(output),
                    preset=f_p
                )

        elif (name and thumbnail) and (final_ext == "mp3"):

            stem, _ = os.path.splitext(name)
            downloaded_aud = folder.joinpath(name)
            output = folder.joinpath(f"{stem.strip('_')}.{final_ext}")
            self.file_convertor.enqueue_audio(
                str(downloaded_aud),
                thumbnail,
                output=str(output),
                ffkwargs=None,  # ToDo: improve encoding speed by maybe using ext
                preset=f_p,
            )

        elif name and (final_ext == "mp4"):

            stem, _ = os.path.splitext(name)
            downloaded_vid = folder.joinpath(name)
            output = folder.joinpath(f"{stem.strip('_')}.{final_ext}")
            self.file_convertor.enqueue_video(
                str(downloaded_vid),
                str(output),
                preset=f_p,
            )

    def _download_error(self, api, gid: str):
        """ callback for download error event """
        name, folder, error_msg = self._on_error(gid)
        logger.error(error_msg)

        if isinstance(name, tuple):
            vidname, audname = name
            # delete partial files
            safe_delete(os.path.join(folder, audname))
            safe_delete(os.path.join(folder, vidname))
        else:
            filename = os.path.join(folder, name)
            safe_delete(filename)
        self.errored_num += 1

    def cancel_download(self, d: aria2p.Download) -> bool:
        """ cancel one download """
        self.active_downloads.pop(d.gid, None)
        return all(self.aria_client.remove([d], force=True, files=True))

    def cancel_all(self) -> bool:
        """ cancel all pending downlaods """
        self.active_downloads.clear()
        try:
            return self.aria_client.remove_all(force=True)
        except Exception as e:
            logger.exception(e)
            return True

    def shutdown_downloader(self, clear=True) -> bool:
        """
        shutdown downloader
        once shutdown it cannot
        be restarted using the same instance
        """

        self.prog_monitor_running = False
        self.process_running = False
        if clear:
            rtv = self.cancel_all()
        else:
            rtv = True
        try:
            self.aria_client.stop_listening()
        except Exception as e:
            logger.exception(e)
        # close file conversion
        self.file_convertor.close()
        try:
            self.aria_process.terminate()  # kill process
        except AttributeError:  # aria_process is None
            pass
        return rtv
