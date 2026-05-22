"""Configuration loader.

Loads TOML and merges into frozen dataclasses with defaults baked in.
Unknown keys raise ValueError so typos surface immediately.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field, fields
from pathlib import Path

# tomllib is stdlib in Python 3.11+. Fall back to the tomli package on 3.10 dev boxes.
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError as e:
        raise ImportError(
            "Python < 3.11 requires the 'tomli' package. "
            "Add `tomli; python_version < \"3.11\"` to requirements.txt."
        ) from e


@dataclass(frozen=True)
class VideoCfg:
    camera_index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 15


@dataclass(frozen=True)
class RecognitionCfg:
    face_threshold: float = 0.55
    uncertain_band: tuple[float, float] = (0.55, 0.65)
    auth_cooldown_s: int = 5
    stranger_cooldown_s: int = 30
    mediapipe_min_conf: float = 0.6
    face_samples_per_user: int = 5


@dataclass(frozen=True)
class LinkCfg:
    port: str = "/dev/ttyUSB0"
    baud: int = 115200
    ping_interval_s: int = 5
    heartbeat_timeout_s: int = 30


@dataclass(frozen=True)
class RecorderCfg:
    pre_seconds: int = 5
    post_seconds: int = 5
    max_age_days: int = 30
    max_total_gb: int = 5
    ffmpeg_timeout_s: int = 30


@dataclass(frozen=True)
class WebCfg:
    host: str = "0.0.0.0"
    port: int = 8080


@dataclass(frozen=True)
class PathsCfg:
    data_dir: str = "/var/lib/smart-gate"
    log_dir: str = "/var/log/smart-gate"


@dataclass(frozen=True)
class LoggingCfg:
    level: str = "INFO"
    rotate_mb: int = 50
    backup_count: int = 5


@dataclass(frozen=True)
class Config:
    video: VideoCfg = field(default_factory=VideoCfg)
    recognition: RecognitionCfg = field(default_factory=RecognitionCfg)
    link: LinkCfg = field(default_factory=LinkCfg)
    recorder: RecorderCfg = field(default_factory=RecorderCfg)
    web: WebCfg = field(default_factory=WebCfg)
    paths: PathsCfg = field(default_factory=PathsCfg)
    logging: LoggingCfg = field(default_factory=LoggingCfg)


def _merge_section(section_name: str, section_cls, raw: dict):
    valid = {f.name for f in fields(section_cls)}
    unknown = set(raw) - valid
    if unknown:
        raise ValueError(
            f"unknown key(s) in [{section_name}]: {sorted(unknown)}"
        )
    coerced = {}
    for f in fields(section_cls):
        if f.name not in raw:
            continue
        val = raw[f.name]
        if isinstance(val, list) and f.name == "uncertain_band":
            val = tuple(val)
        coerced[f.name] = val
    return section_cls(**coerced)


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        return Config()
    with open(path, "rb") as f:
        data = tomllib.load(f)
    section_classes = {f.name: f.default_factory for f in fields(Config)}
    sections = {}
    for name, factory in section_classes.items():
        raw = data.get(name, {})
        sections[name] = _merge_section(name, factory, raw)
    unknown_sections = set(data) - set(section_classes)
    if unknown_sections:
        raise ValueError(f"unknown section(s): {sorted(unknown_sections)}")
    return Config(**sections)
