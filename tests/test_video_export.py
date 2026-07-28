import os
import subprocess

import pytest

from v_ase.export import VIDEO_EXPORT_FORMATS, transcode_video_file, video_export_format


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


def test_video_profiles_prioritize_compact_high_resolution_output():
    mov = VIDEO_EXPORT_FORMATS["mov"]["codec_args"]
    avi = VIDEO_EXPORT_FORMATS["avi"]["codec_args"]
    assert mov[mov.index("-preset") + 1] == "slow"
    assert mov[mov.index("-crf") + 1] == "20"
    assert mov[mov.index("-profile:v") + 1] == "high"
    assert avi[avi.index("-q:v") + 1] == "3"


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


def test_video_transcode_applies_requested_fps_and_exact_frame_count(tmp_path):
    source = tmp_path / "browser-recording.webm"
    make_test_webm(source)

    target, _, _ = transcode_video_file(
        str(source),
        "mov",
        fps=6,
        frame_count=3,
    )
    try:
        import imageio_ffmpeg

        decoded = imageio_ffmpeg.read_frames(target, pix_fmt="rgb24")
        metadata = next(decoded)
        frames = list(decoded)

        assert metadata["fps"] == pytest.approx(6)
        assert len(frames) == 3
    finally:
        if os.path.exists(target):
            os.unlink(target)


def test_video_transcode_reports_monotonic_encoding_progress(tmp_path):
    source = tmp_path / "browser-recording.webm"
    make_test_webm(source)
    updates = []

    target, _, _ = transcode_video_file(
        str(source),
        "mov",
        fps=6,
        frame_count=3,
        progress_callback=lambda ratio, eta, frame: updates.append(
            (ratio, eta, frame)
        ),
    )
    try:
        assert updates
        ratios = [item[0] for item in updates]
        assert ratios == sorted(ratios)
        assert ratios[-1] == pytest.approx(1.0)
        assert updates[-1][1] == pytest.approx(0.0)
        assert updates[-1][2] == 3
    finally:
        if os.path.exists(target):
            os.unlink(target)
