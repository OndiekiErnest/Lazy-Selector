<<<<<<< HEAD
""" app-level core """

import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# use a set to remove duplicates
EXTS = {
    '.mp3', '.m4a', '.aac', '.mp4',
    '.flac', '.avi', '.wav', '.mkv', '.flv',
    '.m2v', '.m3u', '.m4v', '.mpeg1',
    '.mpeg2', '.m1v', '.mpeg4', '.part',
    '.3g2', '.mpeg', '.mpg', '.vob',
    '.mp1', '.ogg', '.mov', '.3gp',
    '.wmv', '.mod', '.mp2', '.amr',
    '.wma', '.mka', '.dat', '.webm',
    '.MP3', '.M4A', '.AAC', '.MP4',
    '.FLAC', '.AVI', '.WAV', '.MKV', '.FLV',
    '.M2V', '.M3U', '.M4V', '.MPEG1',
    '.MPEG2', '.M1V', '.MPEG4', '.PART',
    '.3G2', '.MPEG', '.MPG', '.VOB',
    '.MP1', '.OGG', '.MOV', '.3GP',
    '.WMV', '.MOD', '.MP2', '.AMR',
    '.WMA', '.MKA', '.DAT', '.WEBM',
}


def scroll_widget(event):
    """ event function to bind to mouse wheel for tkinter widgets """
    event.widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
=======
""" app-level core """

import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# use a set to remove duplicates
EXTS = {
    '.mp3', '.m4a', '.aac', '.mp4',
    '.flac', '.avi', '.wav', '.mkv', '.flv',
    '.m2v', '.m3u', '.m4v', '.mpeg1',
    '.mpeg2', '.m1v', '.mpeg4', '.part',
    '.3g2', '.mpeg', '.mpg', '.vob',
    '.mp1', '.ogg', '.mov', '.3gp',
    '.wmv', '.mod', '.mp2', '.amr',
    '.wma', '.mka', '.dat', '.webm',
    '.MP3', '.M4A', '.AAC', '.MP4',
    '.FLAC', '.AVI', '.WAV', '.MKV', '.FLV',
    '.M2V', '.M3U', '.M4V', '.MPEG1',
    '.MPEG2', '.M1V', '.MPEG4', '.PART',
    '.3G2', '.MPEG', '.MPG', '.VOB',
    '.MP1', '.OGG', '.MOV', '.3GP',
    '.WMV', '.MOD', '.MP2', '.AMR',
    '.WMA', '.MKA', '.DAT', '.WEBM',
}


def scroll_widget(event):
    """ event function to bind to mouse wheel for tkinter widgets """
    event.widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
>>>>>>> a4e48a141439482a4b6694fbb454ee0b61de7240
