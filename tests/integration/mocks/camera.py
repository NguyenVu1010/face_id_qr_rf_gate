"""Mock cv2.VideoCapture that yields fixture frames in a loop."""
from __future__ import annotations

from pathlib import Path
import numpy as np


class FakeVideoCapture:
    def __init__(self, frames: list, jpg_quality: int = 75):
        self._frames = frames or [np.zeros((480, 640, 3), dtype=np.uint8)]
        self._i = 0
        self._opened = True

    def isOpened(self) -> bool:
        return self._opened

    def set(self, *args, **kwargs):
        return True

    def read(self):
        if not self._opened:
            return False, None
        frame = self._frames[self._i % len(self._frames)]
        self._i += 1
        return True, frame.copy()

    def release(self):
        self._opened = False


class FakeCV2Module:
    """Drop-in for the cv2 module used inside capture/detector — only the
    properties/functions we touch in tests are implemented."""
    CAP_V4L2 = 0
    CAP_PROP_FOURCC = 6
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4
    CAP_PROP_FPS = 5
    CAP_PROP_BUFFERSIZE = 38
    IMWRITE_JPEG_QUALITY = 1
    COLOR_BGR2RGB = 4
    FONT_HERSHEY_SIMPLEX = 0

    def __init__(self, frames):
        self._frames = frames

    def VideoCapture(self, idx, backend=0):
        return FakeVideoCapture(self._frames)

    def VideoWriter_fourcc(self, *args):
        return 0

    def imencode(self, ext, frame, params=None):
        import numpy as np
        return True, np.frombuffer(b"FAKEJPEG" * 8, dtype=np.uint8)

    def cvtColor(self, frame, code):
        return frame                                # noop for fake

    def rectangle(self, *args, **kwargs): pass
    def putText(self, *args, **kwargs): pass
    def imshow(self, *args, **kwargs): pass
    def namedWindow(self, *args, **kwargs): pass
    def destroyAllWindows(self): pass
    def waitKey(self, *_): return -1
