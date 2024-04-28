<<<<<<< HEAD
""" vlc mixer utils """

import os
from streams.utils import (
    r_path,
)
from core import BASE_DIR

# this section can be commented out so that python-vlc can use path in which vlc app is installed
# uncomment to use the environment variables
VLC_DIR = r_path("mixer", base_dir=BASE_DIR)
DLL_DIR = os.path.join(VLC_DIR, "libvlc.dll")
""" set environment variables for vlc to use """
os.environ.setdefault("PYTHON_VLC_MODULE_PATH", VLC_DIR)
os.environ.setdefault("PYTHON_VLC_LIB_PATH", DLL_DIR)

from vlc import Instance, PlaybackMode, MediaParsedStatus


class VLC():
    """
    python-vlc player
    """

    def __init__(self):
        self._instance = Instance(("--no-video", "--quiet"))
        self.playlist = self._instance.media_list_player_new()
        self.media_list = self._instance.media_list_new()
        self._player = self.playlist.get_media_player()
        self._repeat = False
        self.media = None

    def _release(self):
        # release previous; start a fresh
        try:
            self.playlist.stop()
        except AttributeError:
            pass
        try:
            self.playlist.release()
        except AttributeError:
            pass
        try:
            self.media_list.release()
        except AttributeError:
            pass
        if self.media is not None:
            self.media.release()
        self.media, self.playlist, self.media_list = None, None, None
        self._player = None

    def load(self, filename: str) -> str:
        """
            filename: path of media to be played
            should be called before play()
        """
        self._release()
        self.playlist = self._instance.media_list_player_new()
        self.media_list = self._instance.media_list_new()
        self._player = self.playlist.get_media_player()
        # set playback mode to bool stored in _repeat
        self.loop = self._repeat
        self.media = self._instance.media_new(filename)
        resource = self.media.get_mrl()
        # parser returns 0 on success
        self.media.parse_with_options(1, 0)
        # self.media.parse()
        self.media_list.add_media(self.media)
        self.playlist.set_media_list(self.media_list)
        return resource

    @property
    def duration(self) -> float:
        """
            return media duration in seconds
        """
        # while not self.data_ready:
        if self.media is not None:
            return self.media.get_duration() / 1000

    @property
    def time(self) -> float:
        """
            return elapsed time in seconds
        """
        if self._player is not None:
            return self._player.get_time() / 1000

    def seek(self, pos: float):
        """
            pos: time in ms
        """
        if self._player is not None:
            try:
                self._player.set_time(pos)
            except Exception:
                pass

    def play(self):
        """
            start/resume playing; change mixer state
        """
        if self.playlist is not None:
            self.playlist.play()

    def pause(self):
        """
            pause playback; change state
        """
        if self.playlist is not None:
            self.playlist.pause()

    def stop(self):
        """
            stop playing media
        """
        if self.playlist is not None:
            self.playlist.stop()

    def mute(self, mute: bool):
        """ mute player """
        if self._player is not None:
            self._player.audio_set_mute(mute)

    @property
    def loop(self) -> bool:
        """
            get the playback mode
        """
        return self._repeat

    @loop.setter
    def loop(self, value: bool):
        """
            we use plylist so we can use set playback mode
        """
        if isinstance(value, bool) and self.playlist is not None:
            self._repeat = value
            if self._repeat:
                self.playlist.set_playback_mode(PlaybackMode.loop)
            else:
                self.playlist.set_playback_mode(PlaybackMode.default)

    @property
    def state(self):
        if self.playlist is not None:
            return self.playlist.get_state()

    @property
    def data_ready(self) -> bool:
        if self.media is not None:
            return self.media.get_parsed_status() == MediaParsedStatus.done

    def delete(self):
        """
            release resources
        """
        self._release()
        self._instance.release()
=======
<<<<<<< HEAD
""" vlc mixer utils """

import os
from streams.utils import (
    r_path,
)
from core import BASE_DIR

# this section can be commented out so that python-vlc can use path in which vlc app is installed
# uncomment to use the environment variables
# VLC_DIR = r_path("mixer", base_dir=BASE_DIR)
# DLL_DIR = os.path.join(VLC_DIR, "libvlc.dll")
# """ set environment variables for vlc to use """
# os.environ.setdefault("PYTHON_VLC_MODULE_PATH", VLC_DIR)
# os.environ.setdefault("PYTHON_VLC_LIB_PATH", DLL_DIR)

from vlc import Instance, PlaybackMode, MediaParsedStatus


class VLC():
    """
    python-vlc player
    """

    def __init__(self):
        self._instance = Instance(("--no-video", "--quiet"))
        self.playlist = self._instance.media_list_player_new()
        self.media_list = self._instance.media_list_new()
        self._player = self.playlist.get_media_player()
        self._repeat = False
        self.media = None

    def _release(self):
        # release previous; start a fresh
        try:
            self.playlist.stop()
        except AttributeError:
            pass
        try:
            self.playlist.release()
        except AttributeError:
            pass
        try:
            self.media_list.release()
        except AttributeError:
            pass
        if self.media is not None:
            self.media.release()
        self.media, self.playlist, self.media_list = None, None, None
        self._player = None

    def load(self, filename: str) -> str:
        """
            filename: path of media to be played
            should be called before play()
        """
        self._release()
        self.playlist = self._instance.media_list_player_new()
        self.media_list = self._instance.media_list_new()
        self._player = self.playlist.get_media_player()
        # set playback mode to bool stored in _repeat
        self.loop = self._repeat
        self.media = self._instance.media_new(filename)
        resource = self.media.get_mrl()
        # parser returns 0 on success
        self.media.parse_with_options(1, 0)
        # self.media.parse()
        self.media_list.add_media(self.media)
        self.playlist.set_media_list(self.media_list)
        return resource

    @property
    def duration(self) -> float:
        """
            return media duration in seconds
        """
        # while not self.data_ready:
        if self.media is not None:
            return self.media.get_duration() / 1000

    @property
    def time(self) -> float:
        """
            return elapsed time in seconds
        """
        if self._player is not None:
            return self._player.get_time() / 1000

    def seek(self, pos: float):
        """
            pos: time in ms
        """
        if self._player is not None:
            try:
                self._player.set_time(pos)
            except Exception:
                pass

    def play(self):
        """
            start/resume playing; change mixer state
        """
        if self.playlist is not None:
            self.playlist.play()

    def pause(self):
        """
            pause playback; change state
        """
        if self.playlist is not None:
            self.playlist.pause()

    def stop(self):
        """
            stop playing media
        """
        if self.playlist is not None:
            self.playlist.stop()

    def mute(self, mute: bool):
        """ mute player """
        if self._player is not None:
            self._player.audio_set_mute(mute)

    @property
    def loop(self) -> bool:
        """
            get the playback mode
        """
        return self._repeat

    @loop.setter
    def loop(self, value: bool):
        """
            we use plylist so we can use set playback mode
        """
        if isinstance(value, bool) and self.playlist is not None:
            self._repeat = value
            if self._repeat:
                self.playlist.set_playback_mode(PlaybackMode.loop)
            else:
                self.playlist.set_playback_mode(PlaybackMode.default)

    @property
    def state(self):
        if self.playlist is not None:
            return self.playlist.get_state()

    @property
    def data_ready(self) -> bool:
        if self.media is not None:
            return self.media.get_parsed_status() == MediaParsedStatus.done

    def delete(self):
        """
            release resources
        """
        self._release()
        self._instance.release()
=======
""" vlc mixer utils """

import os
from streams.utils import (
    r_path,
)
from core import BASE_DIR

# this section can be commented out so that python-vlc can use path in which vlc app is installed
# uncomment to use the environment variables
# VLC_DIR = r_path("mixer", base_dir=BASE_DIR)
# DLL_DIR = os.path.join(VLC_DIR, "libvlc.dll")
# """ set environment variables for vlc to use """
# os.environ.setdefault("PYTHON_VLC_MODULE_PATH", VLC_DIR)
# os.environ.setdefault("PYTHON_VLC_LIB_PATH", DLL_DIR)

from vlc import Instance, PlaybackMode, MediaParsedStatus


class VLC():
    """
    python-vlc player
    """

    def __init__(self):
        self._instance = Instance(("--no-video", "--quiet"))
        self.playlist = self._instance.media_list_player_new()
        self.media_list = self._instance.media_list_new()
        self._player = self.playlist.get_media_player()
        self._repeat = False
        self.media = None

    def _release(self):
        # release previous; start a fresh
        try:
            self.playlist.stop()
        except AttributeError:
            pass
        try:
            self.playlist.release()
        except AttributeError:
            pass
        try:
            self.media_list.release()
        except AttributeError:
            pass
        if self.media is not None:
            self.media.release()
        self.media, self.playlist, self.media_list = None, None, None
        self._player = None

    def load(self, filename: str) -> str:
        """
            filename: path of media to be played
            should be called before play()
        """
        self._release()
        self.playlist = self._instance.media_list_player_new()
        self.media_list = self._instance.media_list_new()
        self._player = self.playlist.get_media_player()
        # set playback mode to bool stored in _repeat
        self.loop = self._repeat
        self.media = self._instance.media_new(filename)
        resource = self.media.get_mrl()
        # parser returns 0 on success
        self.media.parse_with_options(1, 0)
        # self.media.parse()
        self.media_list.add_media(self.media)
        self.playlist.set_media_list(self.media_list)
        return resource

    @property
    def duration(self) -> float:
        """
            return media duration in seconds
        """
        # while not self.data_ready:
        if self.media is not None:
            return self.media.get_duration() / 1000

    @property
    def time(self) -> float:
        """
            return elapsed time in seconds
        """
        if self._player is not None:
            return self._player.get_time() / 1000

    def seek(self, pos: float):
        """
            pos: time in ms
        """
        if self._player is not None:
            try:
                self._player.set_time(pos)
            except Exception:
                pass

    def play(self):
        """
            start/resume playing; change mixer state
        """
        if self.playlist is not None:
            self.playlist.play()

    def pause(self):
        """
            pause playback; change state
        """
        if self.playlist is not None:
            self.playlist.pause()

    def stop(self):
        """
            stop playing media
        """
        if self.playlist is not None:
            self.playlist.stop()

    def mute(self, mute: bool):
        """ mute player """
        if self._player is not None:
            self._player.audio_set_mute(mute)

    @property
    def loop(self) -> bool:
        """
            get the playback mode
        """
        return self._repeat

    @loop.setter
    def loop(self, value: bool):
        """
            we use plylist so we can use set playback mode
        """
        if isinstance(value, bool) and self.playlist is not None:
            self._repeat = value
            if self._repeat:
                self.playlist.set_playback_mode(PlaybackMode.loop)
            else:
                self.playlist.set_playback_mode(PlaybackMode.default)

    @property
    def state(self):
        if self.playlist is not None:
            return self.playlist.get_state()

    @property
    def data_ready(self) -> bool:
        if self.media is not None:
            return self.media.get_parsed_status() == MediaParsedStatus.done

    def delete(self):
        """
            release resources
        """
        self._release()
        self._instance.release()
>>>>>>> d36391c7013cb6b9ef61944bc1620bd6ba942f04
>>>>>>> a4e48a141439482a4b6694fbb454ee0b61de7240
