from __future__ import annotations

from pathlib import Path
import sys

from onecut.captions import RenderCopy
from onecut.config import Config
from onecut.errors import OneCutError
from onecut.media import RenderSettings
from onecut.process import run, tool_output


def _video_toolbox_decode_available(ffmpeg: Path) -> bool:
    accelerators = tool_output(ffmpeg, "-hwaccels").splitlines()
    pixel_formats = tool_output(ffmpeg, "-pix_fmts")
    return "videotoolbox" in {line.strip() for line in accelerators} and "videotoolbox_vld" in pixel_formats


def choose_hardware_decode(ffmpeg: Path, settings: RenderSettings) -> bool:
    if not _video_toolbox_decode_available(ffmpeg):
        print("Hardware decoding: unavailable; using software decoding")
        return False
    supported_codecs = {"h264", "hevc"}
    supported_pixel_formats = {"yuv420p", "yuvj420p", "nv12", "yuv420p10le", "p010le"}
    unsupported = [
        source
        for source in settings.sources
        if source.codec_name not in supported_codecs
        or source.pixel_format not in supported_pixel_formats
        or source.rotation != 0
    ]
    if unsupported:
        names = ", ".join(source.path.name for source in unsupported[:3])
        if len(unsupported) > 3:
            names += f", and {len(unsupported) - 3} more"
        print(f"Hardware decoding: software fallback for unsupported source(s): {names}")
        return False

    for source in settings.sources:
        download_format = "p010le" if source.bit_depth > 8 else "nv12"
        result = run(
            [
                ffmpeg,
                "-hide_banner", "-loglevel", "error", "-nostats", "-nostdin",
                "-hwaccel", "videotoolbox",
                "-hwaccel_output_format", "videotoolbox_vld",
                "-i", source.path,
                "-map", "0:v:0",
                "-frames:v", "1",
                "-vf", f"hwdownload,format={download_format}",
                "-f", "null", "-",
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            print(f"Hardware decoding: software fallback for {source.path.name}")
            return False
    print("Hardware decoding: VideoToolbox")
    return True


def build_filter_complex(
    path: Path,
    settings: RenderSettings,
    copy: RenderCopy,
    title_path: Path | None,
    use_hardware_decode: bool,
    title_seconds: float,
) -> None:
    width, height = settings.width, settings.height
    fps = f"{settings.fps.numerator}/{settings.fps.denominator}"
    pixel_format = "yuv420p10le" if settings.ten_bit else "yuv420p"
    overlay_format = "yuv420p10" if settings.ten_bit else "yuv420"
    parts: list[str] = []
    concat_inputs: list[str] = []

    for index, source in enumerate(settings.sources):
        duration = source.duration
        video_filter = f"[{index}:v:0]trim=duration={duration:.6f},setpts=PTS-STARTPTS"
        if use_hardware_decode:
            download_format = "p010le" if source.bit_depth > 8 else "nv12"
            video_filter += f",hwdownload,format={download_format}"
        matches_canvas = (
            source.rotation == 0
            and source.width == width
            and source.height == height
            and source.display_width == width
            and source.display_height == height
        )
        if not matches_canvas:
            video_filter += (
                f",scale={width}:{height}:force_original_aspect_ratio=decrease:"
                "force_divisible_by=2:reset_sar=1:flags=lanczos,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black"
            )
        video_filter += f",setsar=1,fps={fps}"
        if source.hdr:
            video_filter += (
                ",zscale=t=linear:npl=100,format=gbrpf32le,"
                "zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
                f"zscale=t=bt709:m=bt709:r=tv,format={pixel_format}"
            )
        else:
            video_filter += f",format={pixel_format}"
        parts.append(video_filter + f"[clipv{index}]")
        if source.has_audio:
            parts.append(
                f"[{index}:a:0]asetpts=PTS-STARTPTS,"
                "aresample=48000:async=1:first_pts=0,apad,"
                f"atrim=duration={duration:.6f},asetpts=PTS-STARTPTS,"
                "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
                f"[clipa{index}]"
            )
        else:
            parts.append(
                "anullsrc=channel_layout=stereo:sample_rate=48000,"
                f"atrim=duration={duration:.6f},asetpts=PTS-STARTPTS,"
                "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
                f"[clipa{index}]"
            )
        concat_inputs.append(f"[clipv{index}][clipa{index}]")

    parts.append(
        "".join(concat_inputs)
        + f"concat=n={len(settings.sources)}:v=1:a=1[basev][maina]"
    )
    input_index = len(settings.sources)
    if title_path:
        title_input = input_index
        input_index += 1
        parts.extend(
            [
                f"[{title_input}:v]loop=loop=-1:size=1:start=0,"
                f"trim=duration={title_seconds:.3f},setpts=PTS-STARTPTS,"
                f"fps={fps},format={pixel_format}[titlev]",
                "anullsrc=channel_layout=stereo:sample_rate=48000,"
                f"atrim=duration={title_seconds:.3f},asetpts=PTS-STARTPTS,"
                "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[titlea]",
            ]
        )

    previous = "basev"
    for index, caption in enumerate(copy.captions):
        caption_input = input_index
        input_index += 1
        overlay_name = f"caption{index}"
        output_name = f"captioned{index}"
        parts.append(f"[{caption_input}:v]format=rgba[{overlay_name}]")
        parts.append(
            f"[{previous}][{overlay_name}]overlay=0:0:"
            f"enable='between(t,{caption.start:.3f},{caption.end:.3f})':"
            f"eof_action=repeat:repeatlast=1:format={overlay_format}[{output_name}]"
        )
        previous = output_name

    if title_path:
        parts.append(f"[titlev][titlea][{previous}][maina]concat=n=2:v=1:a=1[outv][outa]")
    else:
        parts.extend([f"[{previous}]null[outv]", "[maina]anull[outa]"])
    path.write_text(";\n".join(parts), encoding="utf-8")


def _encoder_arguments(ffmpeg: Path, config: Config, settings: RenderSettings) -> tuple[list[str], bool]:
    if settings.ten_bit:
        software = ["-c:v", "libx265", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p10le"]
    else:
        software = ["-c:v", "libx265", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p"]
    has_video_toolbox = "hevc_videotoolbox" in tool_output(ffmpeg, "-encoders")
    if config.video_encoder in {"auto", "videotoolbox"} and has_video_toolbox:
        if settings.ten_bit:
            return [
                "-c:v", "hevc_videotoolbox", "-profile:v", "main10",
                "-pix_fmt", "p010le", "-b:v", settings.video_bitrate,
            ], True
        return [
            "-c:v", "hevc_videotoolbox", "-profile:v", "main",
            "-pix_fmt", "yuv420p", "-b:v", settings.video_bitrate,
        ], True
    if config.video_encoder == "videotoolbox":
        raise OneCutError("hevc_videotoolbox is not available in this FFmpeg build.")
    return software, False


def render_video(
    ffmpeg: Path,
    ffprobe: Path,
    config: Config,
    settings: RenderSettings,
    copy: RenderCopy,
    title_path: Path | None,
    caption_paths: tuple[Path, ...],
    filter_path: Path,
    output_file: Path,
    partial_file: Path,
) -> None:
    if settings.has_hdr and not settings.has_zscale:
        raise OneCutError(
            "HDR footage was detected, but this FFmpeg build has no zscale filter.\n"
            "Use an FFmpeg build with libzimg/zscale so HDR can be tone-mapped safely."
        )
    use_hardware_decode = choose_hardware_decode(ffmpeg, settings)
    build_filter_complex(
        filter_path,
        settings,
        copy,
        title_path,
        use_hardware_decode,
        config.title_seconds,
    )
    encoder, using_video_toolbox = _encoder_arguments(ffmpeg, config, settings)

    render_inputs: list[str | Path] = []
    for source in settings.sources:
        if use_hardware_decode:
            render_inputs.extend(
                ["-hwaccel", "videotoolbox", "-hwaccel_output_format", "videotoolbox_vld"]
            )
        render_inputs.extend(["-i", source.path])
    if title_path:
        render_inputs.extend(["-i", title_path])
    for caption_path in caption_paths:
        render_inputs.extend(["-i", caption_path])

    output_file.parent.mkdir(parents=True, exist_ok=True)
    partial_file.unlink(missing_ok=True)
    print(f"== Rendering {len(settings.sources)} clips in one high-quality pass ==")

    def attempt(selected_encoder: list[str]) -> int:
        command: list[str | Path] = [
            ffmpeg,
            "-hide_banner", "-loglevel", "error", "-stats", "-nostdin", "-y",
            *render_inputs,
            "-filter_complex_script", filter_path,
            "-map", "[outv]", "-map", "[outa]",
            *selected_encoder,
            "-fps_mode", "cfr", "-tag:v", "hvc1",
            "-color_range", "tv", "-colorspace", "bt709", "-color_trc", "bt709",
            "-color_primaries", "bt709",
            "-bsf:v",
            "hevc_metadata=video_full_range_flag=0:colour_primaries=1:"
            "transfer_characteristics=1:matrix_coefficients=1",
            "-c:a", "aac", "-b:a", "384k", "-ar", "48000", "-ac", "2",
            "-video_track_timescale", "90000", "-movflags", "+faststart",
            partial_file,
        ]
        return run(command).returncode

    result = attempt(encoder)
    if result != 0 and using_video_toolbox and config.video_encoder == "auto":
        print("Hardware encoding failed; retrying with libx265.", file=sys.stderr)
        partial_file.unlink(missing_ok=True)
        software, _ = _encoder_arguments_for_software(settings)
        result = attempt(software)
    if result != 0:
        partial_file.unlink(missing_ok=True)
        raise OneCutError("FFmpeg could not render the output video.")
    partial_file.replace(output_file)

    duration_result = run(
        [
            ffprobe,
            "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", output_file,
        ],
        capture_output=True,
    )
    try:
        duration = int(float((duration_result.stdout or "0").strip()))
    except ValueError:
        duration = 0
    print(f"Done: {output_file} ({duration} seconds)")


def _encoder_arguments_for_software(settings: RenderSettings) -> tuple[list[str], bool]:
    pixel_format = "yuv420p10le" if settings.ten_bit else "yuv420p"
    return [
        "-c:v", "libx265", "-preset", "medium", "-crf", "14", "-pix_fmt", pixel_format
    ], False
