"""
FinGuard — Video Metadata & Media Provenance Analysis Layer
===========================================================
Extracts container, stream, embedded device/camera metadata, and Content
Credentials (C2PA) provenance signals.

Design Principles:
1. Non-blocking: Extraction failures or missing external tools NEVER block or crash the pipeline.
2. Multi-tiered extraction: ffprobe -> ExifTool -> Pure Python/OpenCV fallback.
3. Strict forensic objectivity: Missing metadata or presence of editing software
   (FFmpeg, Premiere Pro, CapCut, etc.) is recorded as an observation only and is
   NEVER classified as AI-generation or fake.
4. Independent signal: Keeps metadata confidence separate from vision/audio deepfake scores.
"""

import os
import sys
import json
import shutil
import struct
import mimetypes
import subprocess
import datetime
from typing import Dict, Any, Optional, List, Tuple

# Fallback MIME types
mimetypes.init()


def _safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if val is None:
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if val is None:
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _parse_fps(fps_str: Any) -> Optional[float]:
    if not fps_str:
        return None
    try:
        if isinstance(fps_str, (int, float)):
            return float(fps_str)
        if "/" in str(fps_str):
            num, den = str(fps_str).split("/", 1)
            den_f = float(den)
            return round(float(num) / den_f, 3) if den_f != 0 else None
        return round(float(fps_str), 3)
    except Exception:
        return None


def _format_bytes(size_bytes: int) -> float:
    return round(size_bytes / (1024 * 1024), 2)


# ── ISO Base Media Box Parser for Pure-Python Fallback & C2PA Scan ───

def _parse_iso_bmff_boxes(file_path: str, max_bytes: int = 50 * 1024 * 1024) -> Dict[str, Any]:
    """
    Parses ISO BMFF (MP4/MOV) boxes natively in pure Python.
    Extracts creation time, duration, brands, and detects C2PA/JUMBF boxes.
    """
    results = {
        "major_brand": None,
        "compatible_brands": [],
        "creation_time_iso": None,
        "modification_time_iso": None,
        "duration_sec": None,
        "c2pa_detected": False,
        "c2pa_box_types": [],
        "has_moov": False,
        "has_ftyp": False,
    }

    C2PA_UUID = b"\xd8\xfe\xc3\xd6\x1b\x0e\x48\x3c\x92\x95\x5e\x26\xec\x87\xfb\x07"

    try:
        if not os.path.exists(file_path):
            return results

        file_size = os.path.getsize(file_path)
        with open(file_path, "rb") as f:
            offset = 0
            while offset < file_size and offset < max_bytes:
                f.seek(offset)
                header = f.read(8)
                if len(header) < 8:
                    break

                box_size, box_type = struct.unpack(">I4s", header)
                header_size = 8

                if box_size == 1:
                    # 64-bit large box
                    large_header = f.read(8)
                    if len(large_header) < 8:
                        break
                    box_size = struct.unpack(">Q", large_header)[0]
                    header_size = 16
                elif box_size == 0:
                    # Box extends to end of file
                    box_size = file_size - offset

                if box_size < header_size:
                    break

                # Check for C2PA / JUMBF boxes
                if box_type in (b"c2pa", b"jumb", b"c2ac"):
                    results["c2pa_detected"] = True
                    results["c2pa_box_types"].append(box_type.decode("latin1", errors="ignore"))
                elif box_type == b"uuid":
                    uuid_bytes = f.read(16)
                    if uuid_bytes == C2PA_UUID:
                        results["c2pa_detected"] = True
                        results["c2pa_box_types"].append("uuid:c2pa")

                # Parse ftyp
                if box_type == b"ftyp" and box_size >= 16:
                    results["has_ftyp"] = True
                    f.seek(offset + header_size)
                    ftyp_payload = f.read(min(box_size - header_size, 64))
                    if len(ftyp_payload) >= 4:
                        results["major_brand"] = ftyp_payload[:4].decode("latin1", errors="ignore").strip()
                        comp_brands = []
                        for i in range(8, len(ftyp_payload), 4):
                            brand = ftyp_payload[i : i + 4].decode("latin1", errors="ignore").strip()
                            if brand:
                                comp_brands.append(brand)
                        results["compatible_brands"] = comp_brands

                # Parse mvhd inside moov
                if box_type == b"moov":
                    results["has_moov"] = True
                    # Search inside moov for mvhd
                    moov_payload_size = min(box_size - header_size, 1024 * 1024)
                    f.seek(offset + header_size)
                    moov_data = f.read(moov_payload_size)

                    # Look for mvhd header
                    mvhd_idx = moov_data.find(b"mvhd")
                    if mvhd_idx != -1 and mvhd_idx >= 4:
                        mvhd_start = mvhd_idx + 4
                        if len(moov_data) >= mvhd_start + 24:
                            version = moov_data[mvhd_start]
                            # ISO time starts from Jan 1, 1904 UTC
                            mac_epoch_offset = 2082844800
                            try:
                                if version == 1 and len(moov_data) >= mvhd_start + 32:
                                    ctime, mtime, timescale, duration = struct.unpack(
                                        ">QQII", moov_data[mvhd_start + 4 : mvhd_start + 28]
                                    )
                                else:
                                    ctime, mtime, timescale, duration = struct.unpack(
                                        ">IIII", moov_data[mvhd_start + 4 : mvhd_start + 20]
                                    )

                                if ctime > mac_epoch_offset:
                                    utc_ctime = datetime.datetime.fromtimestamp(
                                        ctime - mac_epoch_offset, tz=datetime.timezone.utc
                                    )
                                    results["creation_time_iso"] = utc_ctime.isoformat()
                                if mtime > mac_epoch_offset:
                                    utc_mtime = datetime.datetime.fromtimestamp(
                                        mtime - mac_epoch_offset, tz=datetime.timezone.utc
                                    )
                                    results["modification_time_iso"] = utc_mtime.isoformat()
                                if timescale > 0 and duration > 0:
                                    results["duration_sec"] = round(duration / timescale, 2)
                            except Exception:
                                pass

                    # Look for c2pa/jumb inside moov/meta
                    if b"c2pa" in moov_data or b"jumb" in moov_data or C2PA_UUID in moov_data:
                        results["c2pa_detected"] = True
                        if "c2pa_in_moov" not in results["c2pa_box_types"]:
                            results["c2pa_box_types"].append("c2pa_in_moov")

                offset += box_size
    except Exception:
        pass

    return results


# ── Extraction Engine 1: ffprobe ─────────────────────────────────────

def _run_ffprobe(file_path: str, timeout_sec: int = 10) -> Optional[Dict[str, Any]]:
    """Runs ffprobe and returns parsed JSON output."""
    ffprobe_cmd = shutil.which("ffprobe")
    if not ffprobe_cmd:
        return None

    cmd = [
        ffprobe_cmd,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
            check=False
        )
        if proc.returncode == 0 and proc.stdout:
            return json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        pass
    return None


# ── Extraction Engine 2: ExifTool ────────────────────────────────────

def _run_exiftool(file_path: str, timeout_sec: int = 10) -> Optional[Dict[str, Any]]:
    """Runs exiftool and returns parsed JSON dictionary."""
    exiftool_cmd = shutil.which("exiftool")
    if not exiftool_cmd:
        return None

    cmd = [
        exiftool_cmd,
        "-json",
        "-G",
        "-api", "LargeFileSupport=1",
        file_path
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
            check=False
        )
        if proc.returncode == 0 and proc.stdout:
            parsed = json.loads(proc.stdout)
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed[0]
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        pass
    return None


# ── Extraction Engine 3: Python Fallback ──────────────────────────────

def _extract_python_fallback(file_path: str) -> Dict[str, Any]:
    """Pure Python + OpenCV fallback when ffprobe/exiftool are absent."""
    stat_info = os.stat(file_path) if os.path.exists(file_path) else None
    mime_type, _ = mimetypes.guess_type(file_path)

    bmff_info = _parse_iso_bmff_boxes(file_path)

    width = None
    height = None
    fps = None
    nb_frames = None
    duration_sec = bmff_info.get("duration_sec")
    fourcc = None

    try:
        import cv2
        cap = cv2.VideoCapture(file_path)
        if cap.isOpened():
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or None
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or None
            fps_val = cap.get(cv2.CAP_PROP_FPS)
            fps = round(fps_val, 3) if fps_val and fps_val > 0 else None
            frame_cnt = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            nb_frames = frame_cnt if frame_cnt > 0 else None
            if duration_sec is None and fps and nb_frames:
                duration_sec = round(nb_frames / fps, 2)
            fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
            if fourcc_int:
                fourcc = "".join([chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)]).strip()
            cap.release()
    except Exception:
        pass

    return {
        "stat_info": stat_info,
        "mime_type": mime_type or "video/mp4",
        "bmff_info": bmff_info,
        "width": width,
        "height": height,
        "fps": fps,
        "nb_frames": nb_frames,
        "duration_sec": duration_sec,
        "fourcc": fourcc
    }


# ── Provenance & C2PA Detector ───────────────────────────────────────

def _detect_provenance(
    file_path: str,
    ffprobe_data: Optional[Dict[str, Any]],
    exif_data: Optional[Dict[str, Any]],
    bmff_info: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Checks for Content Credentials / C2PA manifests in container boxes,
    XMP namespaces, or EXIF tags.
    """
    provenance_status = "not_available"
    c2pa_manifest_detected = False
    issuer = None
    claim_generator = None
    details: Dict[str, Any] = {}

    # Check 1: BMFF box scanning
    if bmff_info.get("c2pa_detected"):
        c2pa_manifest_detected = True
        provenance_status = "detected"
        details["box_types"] = bmff_info.get("c2pa_box_types", [])

    # Check 2: ExifTool XMP/C2PA tags
    if exif_data:
        for k, v in exif_data.items():
            k_lower = k.lower()
            if "c2pa" in k_lower or "contentcredentials" in k_lower or "jumbf" in k_lower:
                c2pa_manifest_detected = True
                provenance_status = "detected"
                details[k] = v
            if "claimgenerator" in k_lower:
                claim_generator = str(v)
            if "issuer" in k_lower:
                issuer = str(v)

    # Check 3: Raw ffprobe tags
    if ffprobe_data:
        format_tags = ffprobe_data.get("format", {}).get("tags", {})
        for k, v in format_tags.items():
            k_lower = k.lower()
            if "c2pa" in k_lower or "contentcredentials" in k_lower:
                c2pa_manifest_detected = True
                provenance_status = "detected"
                details[k] = v

    # Check 4: Byte-level signature search if not detected yet
    if not c2pa_manifest_detected and os.path.exists(file_path):
        try:
            with open(file_path, "rb") as f:
                # Read first 2MB and last 512KB where manifests typically reside
                head = f.read(2 * 1024 * 1024)
                f.seek(max(0, os.path.getsize(file_path) - 512 * 1024))
                tail = f.read(512 * 1024)
                combined = head + tail
                if b"http://c2pa.org/" in combined or b"c2pa.manifest" in combined or b"C2PA" in combined:
                    c2pa_manifest_detected = True
                    provenance_status = "detected"
                    details["signature"] = "c2pa_xmp_namespace"
        except Exception:
            pass

    return {
        "provenance_status": provenance_status,
        "c2pa_manifest_detected": c2pa_manifest_detected,
        "issuer": issuer,
        "claim_generator": claim_generator,
        "details": details if details else None,
    }


# ── Observations & Completeness Builder ──────────────────────────────

def _build_forensic_observations(
    file_info: Dict[str, Any],
    container_info: Dict[str, Any],
    video_stream: Dict[str, Any],
    audio_stream: Dict[str, Any],
    embedded: Dict[str, Any],
    provenance: Dict[str, Any],
    extraction_sources: List[str]
) -> Tuple[List[str], str, float]:
    """
    Constructs objective forensic observations, completeness tier, and confidence score.
    Follows forensic rules: No accusations or false-positive AI assertions.
    """
    obs: List[str] = []
    points = 0
    max_points = 10

    # 1. Extraction sources
    if not extraction_sources:
        obs.append("Metadata extraction unavailable or external parsers disabled")
        return obs, "low", 0.0

    # 2. Camera hardware tags
    if embedded.get("camera_make") or embedded.get("camera_model") or embedded.get("device_manufacturer"):
        device_str = " / ".join(filter(None, [
            embedded.get("camera_make") or embedded.get("device_manufacturer"),
            embedded.get("camera_model") or embedded.get("device_model")
        ]))
        obs.append(f"Camera/Device hardware metadata present: {device_str}")
        points += 3
    else:
        obs.append("No camera hardware metadata detected (common in web, messaging, and edited re-encodes)")

    # 3. Creation Software & Encoder
    software = embedded.get("software_used") or embedded.get("encoder_software") or video_stream.get("encoder")
    if software:
        obs.append(f"Encoding/Creation software identified: {software}")
        points += 2
        # Check if known editor
        sw_lower = software.lower()
        if any(tool in sw_lower for tool in ["premiere", "after effects", "capcut", "davinci", "final cut", "handbrake", "imovie"]):
            obs.append("Video container indicates processing with video editing / transcoding software")
        elif "lavf" in sw_lower or "ffmpeg" in sw_lower:
            obs.append("Video encoded via FFmpeg / Libavformat multimedia framework")
    else:
        obs.append("No specific encoder or authoring software tag declared in stream headers")

    # 4. Timestamps
    cdate = embedded.get("creation_date")
    mdate = embedded.get("modification_date")
    if cdate:
        obs.append(f"Creation timestamp recorded: {cdate}")
        points += 2
        if mdate and mdate != cdate:
            obs.append(f"Modification timestamp recorded: {mdate}")
    else:
        obs.append("No container creation timestamp preserved")

    # 5. GPS Data
    if embedded.get("gps_coordinates"):
        gps = embedded["gps_coordinates"]
        lat = gps.get("latitude")
        lon = gps.get("longitude")
        obs.append(f"Geographic location coordinates embedded (Lat: {lat}, Lon: {lon})")
        points += 1
    else:
        obs.append("No embedded GPS or geographic coordinates found")

    # 6. Stream resolution and codec
    if video_stream.get("codec_name") and video_stream.get("resolution") != "Unknown":
        res = video_stream.get("resolution")
        fps = video_stream.get("frame_rate")
        codec = video_stream.get("codec_name")
        obs.append(f"Video stream stream: {codec.upper()} at {res} ({fps} fps)")
        points += 2

    # 7. Audio stream
    if audio_stream.get("has_audio"):
        a_codec = audio_stream.get("codec_name") or "audio"
        sr = audio_stream.get("sample_rate_hz")
        ch = audio_stream.get("channels")
        obs.append(f"Audio stream: {a_codec.upper()} ({sr} Hz, {ch} ch)")
        points += 1
    else:
        obs.append("No audio stream present in media container")

    # 8. Provenance / C2PA
    if provenance.get("c2pa_manifest_detected"):
        obs.append(
            "Content Credentials (C2PA) provenance manifest detected: "
            "Certifies media lineage or generative AI asset declarations; distinct from biometric face-swap or manipulation evidence."
        )
        points += 2
    else:
        obs.append("No Content Credentials (C2PA) provenance manifest detected")

    # Completeness calculation
    if points >= 7:
        completeness = "high"
    elif points >= 4:
        completeness = "medium"
    else:
        completeness = "low"

    confidence = round(min(1.0, max(0.1, points / max_points)), 2)

    return obs, completeness, confidence


# ── Main Entrypoint ──────────────────────────────────────────────────

def extract_metadata_forensics(
    video_path: str,
    job_id: str = "default",
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Extracts comprehensive forensic metadata and provenance information for a media file.
    
    Returns:
        dict: Standardized metadata forensics dictionary matching pipeline specifications.
    """
    if config is None:
        try:
            from src.config import get_metadata_config
            config = get_metadata_config()
        except Exception:
            config = {
                "enabled": True,
                "use_ffprobe": True,
                "use_exiftool": True,
                "timeout_seconds": 10,
                "detect_provenance": True
            }

    if not config.get("enabled", True):
        return {
            "status": "unavailable",
            "reason": "Metadata forensics disabled in configuration",
            "completeness": "low",
            "provenance_status": "not_available",
            "forensic_observations": ["Metadata forensics disabled in configuration"],
            "metadata_confidence": 0.0
        }

    if not video_path or not os.path.exists(video_path):
        return {
            "status": "unavailable",
            "reason": f"File not found: {video_path}",
            "completeness": "low",
            "provenance_status": "not_available",
            "forensic_observations": ["Target file does not exist on disk"],
            "metadata_confidence": 0.0
        }

    timeout_sec = config.get("timeout_seconds", 10)
    use_ffprobe = config.get("use_ffprobe", True)
    use_exiftool = config.get("use_exiftool", True)
    detect_prov = config.get("detect_provenance", True)

    extraction_sources: List[str] = []
    ffprobe_data: Optional[Dict[str, Any]] = None
    exif_data: Optional[Dict[str, Any]] = None

    # Step 1: Run ffprobe if enabled
    if use_ffprobe:
        try:
            ffprobe_data = _run_ffprobe(video_path, timeout_sec=timeout_sec)
            if ffprobe_data:
                extraction_sources.append("ffprobe")
        except Exception:
            pass

    # Step 2: Run ExifTool if enabled
    if use_exiftool:
        try:
            exif_data = _run_exiftool(video_path, timeout_sec=timeout_sec)
            if exif_data:
                extraction_sources.append("exiftool")
        except Exception:
            pass

    # Step 3: Pure Python & OpenCV fallback (always available)
    try:
        py_data = _extract_python_fallback(video_path)
        extraction_sources.append("python_fallback")
    except Exception as e:
        py_data = {
            "stat_info": os.stat(video_path) if os.path.exists(video_path) else None,
            "mime_type": "video/mp4",
            "bmff_info": {},
            "width": None,
            "height": None,
            "fps": None,
            "nb_frames": None,
            "duration_sec": None,
            "fourcc": None
        }

    # Step 4: Aggregate File Information
    file_stat = py_data.get("stat_info") or (os.stat(video_path) if os.path.exists(video_path) else None)
    file_size_bytes = file_stat.st_size if file_stat else 0
    file_name = os.path.basename(video_path)
    file_ext = os.path.splitext(file_name)[1].lower()

    file_info = {
        "file_name": file_name,
        "file_extension": file_ext,
        "file_size_bytes": file_size_bytes,
        "file_size_mb": _format_bytes(file_size_bytes),
        "mime_type": py_data.get("mime_type") or mimetypes.guess_type(video_path)[0] or "video/mp4"
    }

    # Step 5: Aggregate Container Information
    format_dict = ffprobe_data.get("format", {}) if ffprobe_data else {}
    bmff = py_data.get("bmff_info", {})

    container_tags = format_dict.get("tags", {})
    if exif_data:
        # Merge pertinent tags
        for k in ["Software", "Encoder", "CompressorName", "MajorBrand", "CompatibleBrands"]:
            for exif_k, v in exif_data.items():
                if exif_k.endswith(k) and exif_k not in container_tags:
                    container_tags[exif_k] = str(v)

    format_name = format_dict.get("format_name") or bmff.get("major_brand") or file_ext.replace(".", "")
    format_long_name = format_dict.get("format_long_name") or f"Container ({format_name})"
    duration_sec = _safe_float(format_dict.get("duration")) or py_data.get("duration_sec")
    bitrate_bps = _safe_float(format_dict.get("bit_rate"))
    overall_bitrate_kbps = round(bitrate_bps / 1000.0, 1) if bitrate_bps else None

    container_info = {
        "format_name": format_name,
        "format_long_name": format_long_name,
        "duration_sec": round(duration_sec, 2) if duration_sec else None,
        "overall_bitrate_kbps": overall_bitrate_kbps,
        "metadata_tags": container_tags
    }

    # Step 6: Aggregate Video Stream Information
    video_stream_raw = None
    audio_stream_raw = None

    if ffprobe_data and "streams" in ffprobe_data:
        for s in ffprobe_data["streams"]:
            c_type = s.get("codec_type")
            if c_type == "video" and video_stream_raw is None:
                video_stream_raw = s
            elif c_type == "audio" and audio_stream_raw is None:
                audio_stream_raw = s

    v_width = _safe_int(video_stream_raw.get("width")) if video_stream_raw else py_data.get("width")
    v_height = _safe_int(video_stream_raw.get("height")) if video_stream_raw else py_data.get("height")
    res_str = f"{v_width}x{v_height}" if v_width and v_height else "Unknown"

    v_fps = _parse_fps(video_stream_raw.get("avg_frame_rate") or video_stream_raw.get("r_frame_rate")) if video_stream_raw else py_data.get("fps")
    v_frames = _safe_int(video_stream_raw.get("nb_frames")) if video_stream_raw else py_data.get("nb_frames")
    v_bitrate = _safe_float(video_stream_raw.get("bit_rate")) if video_stream_raw else None
    v_encoder = (video_stream_raw.get("tags", {}).get("encoder") or
                 container_tags.get("encoder") or
                 container_tags.get("HANDLER_NAME")) if video_stream_raw else None

    video_stream = {
        "codec_name": video_stream_raw.get("codec_name") if video_stream_raw else (py_data.get("fourcc") or "Unknown"),
        "codec_long_name": video_stream_raw.get("codec_long_name") if video_stream_raw else None,
        "profile": video_stream_raw.get("profile") if video_stream_raw else None,
        "resolution": res_str,
        "width": v_width,
        "height": v_height,
        "frame_rate": v_fps,
        "pixel_format": video_stream_raw.get("pix_fmt") if video_stream_raw else None,
        "bitrate_kbps": round(v_bitrate / 1000.0, 1) if v_bitrate else None,
        "encoder": v_encoder,
        "nb_frames": v_frames
    }

    # Step 7: Aggregate Audio Stream Information
    has_audio = audio_stream_raw is not None
    a_bitrate = _safe_float(audio_stream_raw.get("bit_rate")) if audio_stream_raw else None
    a_duration = _safe_float(audio_stream_raw.get("duration")) if audio_stream_raw else None

    audio_stream = {
        "has_audio": has_audio,
        "codec_name": audio_stream_raw.get("codec_name") if audio_stream_raw else None,
        "sample_rate_hz": _safe_int(audio_stream_raw.get("sample_rate")) if audio_stream_raw else None,
        "channels": _safe_int(audio_stream_raw.get("channels")) if audio_stream_raw else None,
        "bitrate_kbps": round(a_bitrate / 1000.0, 1) if a_bitrate else None,
        "duration_sec": round(a_duration, 2) if a_duration else None
    }

    # Step 8: Aggregate Embedded Metadata (Camera, Device, Timestamps, GPS)
    cam_make = None
    cam_model = None
    dev_mfr = None
    dev_model = None
    creation_date = None
    modification_date = None
    software_used = None
    encoder_software = None
    gps_coordinates = None

    # Try ExifTool first
    if exif_data:
        for k, v in exif_data.items():
            k_lower = k.lower()
            if "make" in k_lower and not cam_make:
                cam_make = str(v)
            elif "model" in k_lower and not cam_model:
                cam_model = str(v)
            elif "software" in k_lower and not software_used:
                software_used = str(v)
            elif ("createdate" in k_lower or "creationdate" in k_lower) and not creation_date:
                creation_date = str(v)
            elif ("modifydate" in k_lower or "modificationdate" in k_lower) and not modification_date:
                modification_date = str(v)
            elif "gpslatitude" in k_lower and gps_coordinates is None:
                try:
                    gps_coordinates = {
                        "latitude": exif_data.get("Composite:GPSLatitude") or exif_data.get("GPS:GPSLatitude"),
                        "longitude": exif_data.get("Composite:GPSLongitude") or exif_data.get("GPS:GPSLongitude")
                    }
                except Exception:
                    pass

    # Try container tags / ffprobe
    if not creation_date:
        creation_date = container_tags.get("creation_time") or bmff.get("creation_time_iso")
    if not modification_date:
        modification_date = container_tags.get("modification_time") or bmff.get("modification_time_iso")
    if not software_used:
        software_used = container_tags.get("encoder") or container_tags.get("software") or container_tags.get("ENCODER")
    if not encoder_software:
        encoder_software = container_tags.get("encoder") or v_encoder

    # Parse ISO 6709 GPS string from ffprobe location tag if present (e.g. +37.7749-122.4194/)
    if not gps_coordinates:
        loc_str = container_tags.get("location") or container_tags.get("location-eng")
        if loc_str and isinstance(loc_str, str):
            import re
            m = re.match(r"([+-]\d+\.?\d*)([+-]\d+\.?\d*)", loc_str)
            if m:
                gps_coordinates = {
                    "latitude": float(m.group(1)),
                    "longitude": float(m.group(2))
                }

    embedded_metadata = {
        "camera_make": cam_make,
        "camera_model": cam_model,
        "device_manufacturer": dev_mfr or cam_make,
        "device_model": dev_model or cam_model,
        "creation_date": creation_date,
        "modification_date": modification_date,
        "software_used": software_used,
        "encoder_software": encoder_software,
        "gps_coordinates": gps_coordinates
    }

    # Step 9: Provenance Check (C2PA / Content Credentials)
    provenance = _detect_provenance(video_path, ffprobe_data, exif_data, bmff) if detect_prov else {
        "provenance_status": "not_available",
        "c2pa_manifest_detected": False,
        "issuer": None,
        "claim_generator": None,
        "details": None
    }

    # Step 10: Generate Forensic Observations & Completeness
    observations, completeness, confidence = _build_forensic_observations(
        file_info=file_info,
        container_info=container_info,
        video_stream=video_stream,
        audio_stream=audio_stream,
        embedded=embedded_metadata,
        provenance=provenance,
        extraction_sources=extraction_sources
    )

    status = "available" if len(extraction_sources) > 0 else "unavailable"

    return {
        "status": status,
        "extraction_sources": extraction_sources,
        "file_info": file_info,
        "container_info": container_info,
        "video_stream": video_stream,
        "audio_stream": audio_stream,
        "embedded_metadata": embedded_metadata,
        "provenance": provenance,
        "provenance_status": provenance.get("provenance_status", "not_available"),
        "forensic_observations": observations,
        "completeness": completeness,
        "metadata_confidence": confidence
    }
