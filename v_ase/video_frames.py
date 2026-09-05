"""Deterministic, bounded-memory video encoding from indexed PNG frames."""
from __future__ import annotations

import io
import math
import os
import subprocess
import tempfile
import threading

from PIL import Image

from .export import VideoExportError, video_export_format


class VideoFrameEncoder:
    """Write one exact raster per frame, with timestamps derived from its index.

    Frame uploads apply backpressure through ffmpeg's stdin. The encoder never
    samples wall-clock playback, pads dimensions, or invents missing frames.
    """
    def __init__(self, width: int, height: int, fps: float, frames: int, output_format: str):
        for value in (width, height):
            if isinstance(value, bool) or not isinstance(value, int) or not 64 <= value <= 8192 or value % 2:
                raise ValueError("Video width and height must be even integers from 64 through 8192.")
        if isinstance(frames, bool) or not isinstance(frames, int) or not 1 <= frames <= 1_000_000:
            raise ValueError("Video frame count must be an integer from 1 through 1000000.")
        if isinstance(fps, bool) or not math.isfinite(fps) or not 1 <= fps <= 60:
            raise ValueError("Video fps must be finite and between 1 and 60.")
        import imageio_ffmpeg
        self.width, self.height, self.fps, self.frames = width, height, fps, frames
        self.config = video_export_format(output_format)
        self.count = 0
        self.closed = False
        self.lock = threading.RLock()
        target = tempfile.NamedTemporaryFile(delete=False, suffix=self.config['suffix'])
        self.path = target.name
        target.close()
        self.stderr = tempfile.TemporaryFile()
        command = [imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-y',
                   '-f', 'rawvideo', '-pixel_format', 'rgba', '-video_size', f'{width}x{height}',
                   '-framerate', str(fps), '-i', 'pipe:0', '-an', *self.config['codec_args'], self.path]
        try:
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                            stderr=self.stderr)
        except OSError as exc:
            self.stderr.close()
            os.unlink(self.path)
            raise VideoExportError(f"Could not start the video encoder: {exc}") from exc

    def append(self, index: int, png: bytes):
        with self.lock:
            if self.closed:
                raise ValueError("This video export has already closed.")
            if index != self.count or self.count >= self.frames:
                raise ValueError(f"Expected video frame {self.count}; received {index}. Frames cannot be skipped or repeated.")
            try:
                with Image.open(io.BytesIO(png)) as image:
                    if image.format != 'PNG' or image.size != (self.width, self.height):
                        raise ValueError(f"Every video frame must be a {self.width}x{self.height} PNG.")
                    raster = image.convert('RGBA').tobytes()
            except OSError as exc:
                raise ValueError("Video frame is not a valid PNG.") from exc
            try:
                self.process.stdin.write(raster)
                self.process.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                self.abort()
                raise VideoExportError("The video encoder stopped while accepting a frame.") from exc
            self.count += 1
            return {'frame': index, 'accepted_frames': self.count, 'frame_count': self.frames}

    def finish(self):
        with self.lock:
            if self.closed:
                raise ValueError("This video export has already closed.")
            if self.count != self.frames:
                raise ValueError(f"Video is incomplete: accepted {self.count} of {self.frames} frames.")
            try:
                self.process.stdin.close()
                code = self.process.wait(timeout=1800)
                self.stderr.seek(0)
                detail = self.stderr.read(4000).decode('utf-8', errors='replace').strip()
                if code != 0 or not os.path.getsize(self.path):
                    raise VideoExportError(f"Video encoding failed: {detail or code}")
                self.closed = True
                self.stderr.close()
                return self.path, self.config['filename'], self.config['media_type']
            except (OSError, subprocess.TimeoutExpired, VideoExportError) as exc:
                self.abort()
                raise VideoExportError(f"Video could not be finalized: {exc}") from exc

    def abort(self):
        # Kill first to release a writer blocked on pipe backpressure.
        self.closed = True
        if self.process.poll() is None:
            self.process.kill()
        with self.lock:
            try:
                self.process.stdin.close()
            except OSError:
                pass
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            self.stderr.close()
            try:
                os.unlink(self.path)
            except FileNotFoundError:
                pass
