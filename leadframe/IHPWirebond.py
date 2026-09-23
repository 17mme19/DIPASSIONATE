"""Extract provenance-aware wire-bond evidence from an IHP bondplan."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class WireBondMapping:
    pin: int
    die_pad: str
    die_xy_um: Tuple[float, float]
    package_xy_um: Tuple[float, float]
    length_um: float
    angle_deg: float
    skew_deg: float
    min_gap_um: float


@dataclass(frozen=True)
class IHPWireBondRequirements:
    design: str
    package_name: str
    wire_material: Optional[str]
    wire_diameter_um: Optional[float]
    observed_wire_length_min_um: Optional[float]
    observed_wire_length_max_um: Optional[float]
    configured_max_wire_length_um: Optional[float]
    minimum_wire_gap_um: Optional[float]
    configured_guard_spacing_um: Optional[float]
    observed_max_lead_skew_deg: Optional[float]
    configured_max_lead_skew_deg: Optional[float]
    pad_pitch_um: Optional[float]
    pad_opening_um: Optional[float]
    die_orientation: Optional[str]
    die_attach: Optional[str]
    loop_height_um: Optional[float]
    exposed_pad_downbond_count: int
    mappings: Tuple[WireBondMapping, ...]
    sources: Tuple[str, ...]

    @property
    def mapping_by_pin(self) -> Dict[int, WireBondMapping]:
        return {mapping.pin: mapping for mapping in self.mappings}


def extract_ihp_wirebond_requirements(
    config_path: str | Path,
    report_path: str | Path,
) -> IHPWireBondRequirements:
    """Extract the stable wire-bond fields emitted by the IHP bondplan flow."""
    config = Path(config_path).read_text(encoding="utf-8")
    report = Path(report_path).read_text(encoding="utf-8")

    summary = _section(report, "## Summary", "## Bond Table")
    mappings = _parse_mappings(_section(report, "## Bond Table", None))
    values = {
        "design": _required_text(summary, r"\| Design \| ([^|]+) \|"),
        "package_name": _required_text(summary, r"\| Package \| ([^|]+) \|"),
        "wire_material": _config_wire_material(config),
        "wire_diameter_um": _number(config, r"BONDWIRE_WIDTH:\s*([\d.]+)"),
        "observed_wire_length_min_um": _range_min(summary, r"\| Wire length \| ([\d.]+) \.\. ([\d.]+) um"),
        "observed_wire_length_max_um": _range_max(summary, r"\| Wire length \| ([\d.]+) \.\. ([\d.]+) um"),
        "configured_max_wire_length_um": _number(config, r"BONDWIRE_MAX_LENGTH:\s*([\d.]+)"),
        "minimum_wire_gap_um": _number(summary, r"\| Min wire-to-wire gap \| ([\d.]+) um"),
        "configured_guard_spacing_um": _number(config, r"GUARD_SPACING:\s*([\d.]+)"),
        "observed_max_lead_skew_deg": _number(summary, r"\| Max lead skew \| ([\d.]+) deg"),
        "configured_max_lead_skew_deg": _number(config, r"BONDWIRE_MAX_SKEW:\s*([\d.]+)"),
        "pad_pitch_um": _pair_first(summary, r"\| Pad pitch / opening \| ([\d.]+) / ([\d.]+) um"),
        "pad_opening_um": _pair_second(summary, r"\| Pad pitch / opening \| ([\d.]+) / ([\d.]+) um"),
        "die_orientation": _config_text(config, r"orientation:\s*([A-Z]+)"),
        "die_attach": _config_text(config, r'"Die Attach":\s*"([^"]+)"'),
    }
    bondwire_line = re.search(
        r"\| Bondwires \| (\d+) \((\d+) to leads, (\d+) exposed-pad downbonds\) \|",
        summary,
    )
    if bondwire_line is None:
        raise ValueError("IHP bondplan summary is missing the Bondwires row")

    return IHPWireBondRequirements(
        **values,
        exposed_pad_downbond_count=int(bondwire_line.group(3)),
        loop_height_um=None,
        mappings=tuple(mappings),
        sources=(str(Path(config_path)), str(Path(report_path))),
    )


def _section(text: str, start_marker: str, end_marker: Optional[str]) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise ValueError(f"Missing IHP report section: {start_marker}")
    start += len(start_marker)
    end = text.find(end_marker, start) if end_marker else -1
    return text[start:] if end < 0 else text[start:end]


def _required_text(text: str, pattern: str) -> str:
    value = _config_text(text, pattern)
    if value is None:
        raise ValueError(f"Missing IHP bondplan value matching {pattern}")
    return value


def _config_text(text: str, pattern: str) -> Optional[str]:
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1).strip() if match else None


def _number(text: str, pattern: str) -> Optional[float]:
    value = _config_text(text, pattern)
    return float(value) if value is not None else None


def _range_min(text: str, pattern: str) -> Optional[float]:
    match = re.search(pattern, text)
    return float(match.group(1)) if match else None


def _range_max(text: str, pattern: str) -> Optional[float]:
    match = re.search(pattern, text)
    return float(match.group(2)) if match else None


def _pair_first(text: str, pattern: str) -> Optional[float]:
    match = re.search(pattern, text)
    return float(match.group(1)) if match else None


def _pair_second(text: str, pattern: str) -> Optional[float]:
    match = re.search(pattern, text)
    return float(match.group(2)) if match else None


def _config_wire_material(config: str) -> Optional[str]:
    value = _config_text(config, r'"Wire":\s*"([^,"]+),')
    return value.lower() if value else None


def _parse_mappings(section: str) -> list[WireBondMapping]:
    mappings = []
    row_pattern = re.compile(
        r"\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*"
        r"([-\d.]+)\s*/\s*([-\d.]+)\s*\|\s*"
        r"([-\d.]+)\s*/\s*([-\d.]+)\s*\|\s*"
        r"([-\d.]+)\s*\|\s*([-\d.]+)\s*\|\s*"
        r"([-\d.]+)\s*\|\s*([-\d.]+)\s*\|"
    )
    for match in row_pattern.finditer(section):
        mappings.append(
            WireBondMapping(
                pin=int(match.group(1)),
                die_pad=match.group(2).strip(),
                die_xy_um=(float(match.group(3)), float(match.group(4))),
                package_xy_um=(float(match.group(5)), float(match.group(6))),
                length_um=float(match.group(7)),
                angle_deg=float(match.group(8)),
                skew_deg=float(match.group(9)),
                min_gap_um=float(match.group(10)),
            )
        )
    if not mappings:
        raise ValueError("IHP bondplan report contains no bond table rows")
    return mappings
