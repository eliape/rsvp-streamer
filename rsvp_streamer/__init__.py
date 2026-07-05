"""rsvp_streamer — stream text using rapid serial visual presentation (RSVP)."""

from .exceptions import StreamError
from .models import StreamOutput
from .player import StreamPlayer
from .streamer import WordStreamer

__all__ = ["WordStreamer", "StreamPlayer", "StreamOutput", "StreamError"]
