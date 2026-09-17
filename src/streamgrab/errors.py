class StreamGrabError(Exception):
    exit_code = 2


class InputError(StreamGrabError):
    exit_code = 2


class NoPublicStreamError(StreamGrabError):
    exit_code = 3


class NetworkError(StreamGrabError):
    exit_code = 4


class SiteChangedError(StreamGrabError):
    exit_code = 4


class DownloaderError(StreamGrabError):
    exit_code = 5

