from yt_search.search import (
    Search,
    VideosSearch,
    ChannelsSearch,
    PlaylistsSearch,
    CustomSearch,
    ChannelSearch,
)
from yt_search.extras import (
    Video,
    Playlist,
    Suggestions,
    Hashtag,
    Comments,
    Transcript,
    Channel,
)
from yt_search.streamurlfetcher import StreamURLFetcher
from yt_search.core.constants import *
from yt_search.core.utils import playlist_from_channel_id


__title__ = "youtube-search-python"
__version__ = "1.6.2"
__author__ = "alexmercerind"
__license__ = "MIT"


""" Deprecated. Present for legacy support. """
from yt_search.legacy import SearchVideos, SearchPlaylists
from yt_search.legacy import SearchVideos as searchYoutube
