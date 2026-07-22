import os
import subprocess

import pytest

from v_ase.export import transcode_video_file, video_export_format


def make_test_webm(path):
    imageio_ffmpeg = pytest.importorskip("imageio_ffmpeg")
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-f", "lavfi",
        "-i", "testsrc2=size=320x240:rate=6:duration=0.6",
        "-c:v", "libvpx-vp9",
        str(path),
    ]
    subprocess.run(command, check=True, capture_output=True)


def test_video_export_format_rejects_unknown_container():
    assert video_export_format("mov")["media_type"] == "video/quicktime"
    assert video_export_format("AVI")["media_type"] == "video/x-msvideo"
    with pytest.raises(ValueError, match="Unsupported video format"):
        video_export_format("mp4")


@pytest.mark.parametrize(
    ("output_format", "suffix", "media_type", "codec_name"),
    [
        ("mov", ".mov", "video/quicktime", "h264"),
        ("avi", ".avi", "video/x-msvideo", "mpeg4"),
    ],
)
def test_browser_webm_transcodes_to_selected_video_container(
    tmp_path, output_format, suffix, media_type, codec_name
):
    source = tmp_path / "browser-recording.webm"
    make_test_webm(source)

    target, filename, actual_media_type = transcode_video_file(str(source), output_format)
    try:
        assert target.endswith(suffix)
        assert filename.endswith(suffix)
        assert actual_media_type == media_type
        assert os.path.getsize(target) > 500

        import imageio_ffmpeg

        probe = subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", target],
            check=False,
            capture_output=True,
            text=True,
        )
        assert codec_name in probe.stderr.lower()
        assert "320x240" in probe.stderr
    finally:
        if os.path.exists(target):
            os.unlink(target)
