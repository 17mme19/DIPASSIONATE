# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026  <Jochen Zeitler>
"""
PackageDatabase
===============
Parametric IC package catalogue based on JEDEC / IPC standards.

All dimensions are in mm.  Each entry produces a config dict compatible
with ``core.leadframe.build_leadframe()``.

Package families
----------------
  QFN   JEDEC MO-220  —  Quad Flat No-lead, square and rectangular
  QFP   JEDEC MS-026  —  Quad Flat Package (gull-wing)
  DIP   JEDEC MS-001  —  Dual In-line Package (modelled as QFP with 2 sides)
  SOIC  JEDEC MS-012  —  Small Outline IC
  TSSOP JEDEC MO-153  —  Thin Shrink Small Outline Package
  BGA   JEDEC MS-034  —  Ball Grid Array

Usage
-----
    from leadframe.PackageDatabase import search_packages, get_config

    results = search_packages("QFN-24")        # → [PackageSpec, …]
    cfg     = results[0].to_leadframe_config() # → dict for build_leadframe()

    # or: iterate all
    from leadframe.PackageDatabase import ALL_PACKAGES
"""

from __future__ import annotations
from dataclasses import dataclass, field
import os
from pathlib import Path
import importlib.util
import sys
from typing import Optional, List, Tuple

try:
    from .IHPWirebond import extract_ihp_wirebond_requirements
except ImportError:
    _IHP_MODULE_PATH = Path(__file__).with_name("IHPWirebond.py")
    _IHP_SPEC = importlib.util.spec_from_file_location(
        "ihp_wirebond_catalog_source", _IHP_MODULE_PATH
    )
    assert _IHP_SPEC and _IHP_SPEC.loader
    _IHP_MODULE = importlib.util.module_from_spec(_IHP_SPEC)
    sys.modules[_IHP_SPEC.name] = _IHP_MODULE
    _IHP_SPEC.loader.exec_module(_IHP_MODULE)
    extract_ihp_wirebond_requirements = (
        _IHP_MODULE.extract_ihp_wirebond_requirements
    )


# ── data container ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PackageRequirements:
    """User-supplied constraints used in addition to extracted chip data."""

    max_body_height_mm: Optional[float] = None
    max_die_thickness_mm: Optional[float] = None
    require_die_paddle: bool = False
    require_open_cavity: bool = False
    max_power_w: Optional[float] = None
    max_theta_ja_c_per_w: Optional[float] = None
    required_max_junction_temp_c: Optional[float] = None
    rf_frequency_ghz: Optional[float] = None
    require_rf_capable: bool = False
    require_exposed_ground: bool = False
    required_wire_length_mm: Optional[float] = None
    wire_material: Optional[str] = None
    wire_diameter_um: Optional[float] = None
    max_wire_length_mm: Optional[float] = None
    min_wire_gap_um: Optional[float] = None
    max_bond_angle_deg: Optional[float] = None
    max_lead_skew_deg: Optional[float] = None
    require_hermetic: bool = False


@dataclass
class PackageSpec:
    """One standardised package variant."""

    name:         str            # canonical name, e.g. "QFN-24"
    family:       str            # "QFN" | "QFP" | "DIP" | "SOIC" | "TSSOP" | "BGA"
    standard:     str            # JEDEC / IPC reference
    description:  str            # human-readable

    # Body
    body_length_mm:    float     # X  (frame_length)
    body_width_mm:     float     # Y  (frame_width)
    body_height_mm:    float     # Z  (frame_thickness)

    # QFN / QFP / DIP / SOIC / TSSOP — lead geometry
    total_pins:        int       = 0
    pins_lr:           int       = 0      # pins per left / right side
    pins_tb:           int       = 0      # pins per top  / bottom side (0 for 2-sided)
    lead_pitch_mm:     float     = 0.5
    lead_width_mm:     float     = 0.25
    inner_lead_mm:     float     = 0.4    # bond-finger depth inside body
    outer_lead_mm:     float     = 0.6    # gull-wing length (QFP/SOIC only)
    has_die_paddle:    bool      = True
    paddle_length_mm:  float     = 0.0   # 0 → auto (55% of body)
    paddle_width_mm:   float = 0.0
    body_length_min_mm: Optional[float] = None
    body_length_max_mm: Optional[float] = None
    body_width_min_mm:  Optional[float] = None
    body_width_max_mm:  Optional[float] = None
    body_height_min_mm: Optional[float] = None
    body_height_max_mm: Optional[float] = None
    cavity_length_mm: Optional[float] = None
    cavity_width_mm: Optional[float] = None
    die_clearance_x_mm: Optional[float] = None
    die_clearance_y_mm: Optional[float] = None
    max_die_thickness_mm: Optional[float] = None
    die_fit_provenance: str = ""
    paddle_length_min_mm: Optional[float] = None
    paddle_length_max_mm: Optional[float] = None
    paddle_width_min_mm:  Optional[float] = None
    paddle_width_max_mm:  Optional[float] = None

    # Validated capability data. None means the catalogue has no claim.
    max_power_w:             Optional[float] = None
    theta_ja_c_per_w:        Optional[float] = None
    theta_jc_c_per_w:        Optional[float] = None
    max_junction_temp_c:     Optional[float] = None
    rf_capable:              bool = False
    rf_max_frequency_ghz:    Optional[float] = None
    rf_application_frequency_ghz: Optional[float] = None
    exposed_ground:          bool = False
    max_wire_length_mm:      Optional[float] = None
    hermetic:                bool = False
    thermal_enhanced:        bool = False

    # BGA — ball geometry
    bga_ball_dia_mm:   float     = 0.0
    bga_ball_pitch_mm: float     = 0.0

    # Display
    tags:  List[str]  = field(default_factory=list)  # e.g. ["RF", "open-cavity"]
    datasheet_url: str = ""   # direct link to a PDF datasheet, if known
    source_reference: str = ""
    source_revision: str = ""
    land_pattern_length_mm: Optional[float] = None
    land_pattern_width_mm: Optional[float] = None
    exposed_pad_land_length_mm: Optional[float] = None
    exposed_pad_land_width_mm: Optional[float] = None
    solder_paste_length_mm: Optional[float] = None
    solder_paste_width_mm: Optional[float] = None
    occupied_area_length_mm: Optional[float] = None
    occupied_area_width_mm: Optional[float] = None
    application_name: str = ""
    application_supply_min_v: Optional[float] = None
    application_supply_max_v: Optional[float] = None
    application_ambient_min_c: Optional[float] = None
    application_ambient_max_c: Optional[float] = None
    application_power_limit_w: Optional[float] = None
    exposed_pad_grounded: bool = False
    thermal_vias_recommended: bool = False
    wire_material: Optional[str] = None
    wire_diameter_um: Optional[float] = None
    max_wire_length_mm: Optional[float] = None
    min_wire_gap_um: Optional[float] = None
    max_bond_angle_deg: Optional[float] = None
    max_lead_skew_deg: Optional[float] = None
    supports_exposed_pad_downbond: bool = False
    wirebond_provenance: str = "unknown"

    # ── derived ────────────────────────────────────────────────────────────

    @property
    def frame_type_str(self) -> str:
        if self.family in ("QFN",):
            return "QFN (Quad Flat No-lead)"
        if self.family in ("QFP", "DIP", "SOIC", "TSSOP"):
            return "QFP (Quad Flat Package)"
        if self.family == "BGA":
            return "BGA (Ball Grid Array)"
        return self.family

    @property
    def wirebond_status(self) -> str:
        """Human-readable confidence state for wire-bond metadata."""
        if self.wirebond_provenance == "validated":
            return "Validated from IHP bondplan"
        if self.wirebond_provenance == "reference":
            return "Reference data; source report unavailable"
        if any(
            value is not None
            for value in (
                self.wire_material,
                self.wire_diameter_um,
                self.max_wire_length_mm,
                self.min_wire_gap_um,
                self.max_lead_skew_deg,
            )
        ):
            return "Partially documented"
        return "Unknown / requires assembly confirmation"

    def to_leadframe_config(self, material: str = "Copper") -> dict:
        """Return a dict ready for ``core.leadframe.build_leadframe()``."""
        cfg: dict = {
            "frame_type":      self.frame_type_str,
            "frame_length":    self.body_length_mm,
            "frame_width":     self.body_width_mm,
            "frame_thickness": self.body_height_mm,
            "material":        material,
        }
        if self.family in ("QFN", "QFP", "DIP", "SOIC", "TSSOP"):
            # For 2-sided packages (DIP, SOIC) pins_tb = 0 → no top/bottom leads
            cfg.update({
                "left_lead_count":   self.pins_lr,
                "right_lead_count":  self.pins_lr,
                "top_lead_count":    self.pins_tb,
                "bottom_lead_count": self.pins_tb,
                "lead_width":        self.lead_width_mm,
                "lead_pitch":        self.lead_pitch_mm,
                "inner_lead_length": self.inner_lead_mm,
                "lead_length":       self.outer_lead_mm,
                "qfn_pad_thickness": self.body_height_mm,
                "has_die_paddle":    self.has_die_paddle,
                "die_paddle_length": self.paddle_length_mm or round(self.body_length_mm * 0.55, 3),
                "die_paddle_width":  self.paddle_width_mm  or round(self.body_width_mm  * 0.55, 3),
            })
        elif self.family == "BGA":
            cfg.update({
                "bga_ball_diameter": self.bga_ball_dia_mm,
                "bga_ball_pitch":    self.bga_ball_pitch_mm,
            })
        return cfg

    def summary(self) -> str:
        """Single-line summary for display in the UI."""
        if self.family == "BGA":
            return (f"{self.name}  —  {self.body_length_mm}×{self.body_width_mm}×"
                    f"{self.body_height_mm} mm  |  ⌀{self.bga_ball_dia_mm} mm balls "
                    f"@ {self.bga_ball_pitch_mm} mm pitch  [{self.standard}]")
        two_sided = self.pins_tb == 0
        pin_desc  = (f"{self.pins_lr}×2={self.total_pins} pins  pitch={self.lead_pitch_mm} mm"
                     if two_sided else
                     f"{self.pins_lr}×L/R + {self.pins_tb}×T/B  pitch={self.lead_pitch_mm} mm")
        return (f"{self.name}  —  {self.body_length_mm}×{self.body_width_mm}×"
                f"{self.body_height_mm} mm  |  {pin_desc}  [{self.standard}]")


# ── JEDEC / IPC catalogue ──────────────────────────────────────────────────────
#
# Sources:
#   JEDEC MO-220   QFN (Quad Flat No-lead)
#   JEDEC MS-026   QFP (Quad Flat Package)
#   JEDEC MS-001   DIP (Dual In-line Package)
#   JEDEC MS-012   SOIC (Small Outline IC)
#   JEDEC MO-153   TSSOP (Thin Shrink Small Outline Package)
#   JEDEC MS-034   BGA (Ball Grid Array)
#   IPC-7351B      Land pattern guidelines
#
# Dimensions are nominal (not minimum/maximum).  "inner_lead_mm" is
# approximated as body_width/2 * 0.4 for QFN, or standard finger depth.

ALL_PACKAGES: List[PackageSpec] = [

    # ══════════════════════════════════════════════════════
    # QFN  (JEDEC MO-220)
    # ══════════════════════════════════════════════════════

    PackageSpec("QFN-8",  "QFN", "JEDEC MO-220",
                "8-lead 2×2 mm QFN, 0.5 mm pitch",
                body_length_mm=2.0, body_width_mm=2.0, body_height_mm=0.9,
                total_pins=8, pins_lr=2, pins_tb=2,
                lead_pitch_mm=0.50, lead_width_mm=0.25, inner_lead_mm=0.30,
                paddle_length_mm=1.40, paddle_width_mm=1.40),

    PackageSpec("QFN-12", "QFN", "JEDEC MO-220",
                "12-lead 3×3 mm QFN, 0.65 mm pitch",
                body_length_mm=3.0, body_width_mm=3.0, body_height_mm=0.9,
                total_pins=12, pins_lr=3, pins_tb=3,
                lead_pitch_mm=0.65, lead_width_mm=0.30, inner_lead_mm=0.40,
                paddle_length_mm=1.70, paddle_width_mm=1.70),

    PackageSpec("QFN-16", "QFN", "JEDEC MO-220",
                "16-lead 4×4 mm QFN, 0.65 mm pitch",
                body_length_mm=4.0, body_width_mm=4.0, body_height_mm=0.9,
                total_pins=16, pins_lr=4, pins_tb=4,
                lead_pitch_mm=0.65, lead_width_mm=0.30, inner_lead_mm=0.40,
                paddle_length_mm=2.60, paddle_width_mm=2.60),

    PackageSpec("QFN-20", "QFN", "JEDEC MO-220",
                "20-lead 4×4 mm QFN, 0.5 mm pitch",
                body_length_mm=4.0, body_width_mm=4.0, body_height_mm=0.9,
                total_pins=20, pins_lr=5, pins_tb=5,
                lead_pitch_mm=0.50, lead_width_mm=0.25, inner_lead_mm=0.40,
                paddle_length_mm=2.60, paddle_width_mm=2.60),

    PackageSpec("QFN-24", "QFN", "JEDEC MO-220",
                "24-lead 4×4 mm QFN, 0.5 mm pitch",
                body_length_mm=4.0, body_width_mm=4.0, body_height_mm=0.9,
                total_pins=24, pins_lr=6, pins_tb=6,
                lead_pitch_mm=0.50, lead_width_mm=0.25, inner_lead_mm=0.40,
                paddle_length_mm=2.50, paddle_width_mm=2.50),

    PackageSpec("QFN-28", "QFN", "JEDEC MO-220",
                "28-lead 5×5 mm QFN, 0.5 mm pitch",
                body_length_mm=5.0, body_width_mm=5.0, body_height_mm=0.9,
                total_pins=28, pins_lr=7, pins_tb=7,
                lead_pitch_mm=0.50, lead_width_mm=0.25, inner_lead_mm=0.45,
                paddle_length_mm=3.50, paddle_width_mm=3.50),

    PackageSpec("QFN-32", "QFN", "JEDEC MO-220",
                "32-lead 5×5 mm QFN, 0.5 mm pitch",
                body_length_mm=5.0, body_width_mm=5.0, body_height_mm=0.9,
                total_pins=32, pins_lr=8, pins_tb=8,
                lead_pitch_mm=0.50, lead_width_mm=0.25, inner_lead_mm=0.45,
                paddle_length_mm=3.40, paddle_width_mm=3.40),

    PackageSpec(
        "HVQFN32-5X5-FSV9522", "QFN", "HVQFN",
        "32-lead thermal-enhanced 5×5×0.85 mm QFN reference variant",
        body_length_mm=5.0, body_width_mm=5.0, body_height_mm=0.85,
        total_pins=32, pins_lr=8, pins_tb=8,
        lead_pitch_mm=0.50, lead_width_mm=0.25, inner_lead_mm=0.45,
        paddle_length_mm=3.25, paddle_width_mm=3.25,
        body_length_min_mm=4.9, body_length_max_mm=5.1,
        body_width_min_mm=4.9, body_width_max_mm=5.1,
        body_height_min_mm=0.8, body_height_max_mm=0.85,
        paddle_length_min_mm=2.88, paddle_length_max_mm=3.25,
        paddle_width_min_mm=2.88, paddle_width_max_mm=3.25,
        max_power_w=0.20, theta_ja_c_per_w=40.0,
        max_junction_temp_c=100.0,
        rf_capable=True, rf_application_frequency_ghz=0.01356,
        thermal_enhanced=True,
        tags=["RF", "thermal-enhanced", "exposed-pad"],
        datasheet_url="https://www.nxp.com/docs/en/package-information/SOT617-1.pdf",
        source_reference="FSV9522 Standard 3V MIFARE reader solution",
        source_revision="Product data sheet Rev. 2.0, 17 Sep 2014",
    ),

    PackageSpec(
        "HVQFN32-5X5-NXP-SOT617-1", "QFN", "HVQFN",
        "NXP SOT617-1 thermal-enhanced 5×5×0.85 mm QFN reference variant",
        body_length_mm=5.0, body_width_mm=5.0, body_height_mm=0.85,
        total_pins=32, pins_lr=8, pins_tb=8,
        lead_pitch_mm=0.50, lead_width_mm=0.24, inner_lead_mm=0.45,
        paddle_length_mm=3.25, paddle_width_mm=3.25,
        body_length_min_mm=4.9, body_length_max_mm=5.1,
        body_width_min_mm=4.9, body_width_max_mm=5.1,
        body_height_min_mm=0.85, body_height_max_mm=1.0,
        paddle_length_min_mm=2.95, paddle_length_max_mm=3.25,
        paddle_width_min_mm=2.95, paddle_width_max_mm=3.25,
        thermal_enhanced=True,
        tags=["thermal-enhanced", "exposed-pad", "PCB-reference"],
        datasheet_url="https://www.nxp.com/docs/en/package-information/SOT617-1.pdf",
        source_reference="NXP SOT617-1 HVQFN32 Package Information",
        source_revision="12 Jul 2021",
        land_pattern_length_mm=5.3,
        land_pattern_width_mm=5.3,
        exposed_pad_land_length_mm=3.1,
        exposed_pad_land_width_mm=3.1,
        solder_paste_length_mm=1.8,
        solder_paste_width_mm=1.8,
        occupied_area_length_mm=6.25,
        occupied_area_width_mm=6.25,
    ),

    PackageSpec(
        "HVQFN32-5X5-SC16C550B", "QFN", "HVQFN",
        "SC16C550B application reference using NXP SOT617-1 HVQFN32",
        body_length_mm=5.0, body_width_mm=5.0, body_height_mm=0.85,
        total_pins=32, pins_lr=8, pins_tb=8,
        lead_pitch_mm=0.50, lead_width_mm=0.24, inner_lead_mm=0.45,
        paddle_length_mm=3.25, paddle_width_mm=3.25,
        body_length_min_mm=4.9, body_length_max_mm=5.1,
        body_width_min_mm=4.9, body_width_max_mm=5.1,
        body_height_min_mm=0.85, body_height_max_mm=1.0,
        paddle_length_min_mm=2.95, paddle_length_max_mm=3.25,
        paddle_width_min_mm=2.95, paddle_width_max_mm=3.25,
        max_power_w=0.50, max_junction_temp_c=100.0,
        thermal_enhanced=True,
        tags=["thermal-enhanced", "exposed-pad", "application-reference"],
        source_reference="NXP SC16C550B product data sheet",
        source_revision="Rev. 6, 16 Dec 2014",
        application_name="SC16C550B UART",
        application_supply_min_v=2.5,
        application_supply_max_v=5.0,
        application_ambient_min_c=-40.0,
        application_ambient_max_c=85.0,
        application_power_limit_w=0.50,
        exposed_pad_grounded=True,
        thermal_vias_recommended=True,
    ),

    PackageSpec(
        "OP-QFN32-A4-FIT-IHP", "QFN", "EUROPRACTICE",
        "IHP SG13G2 OP_QFN32_A4_FIT bondplan reference package",
        body_length_mm=5.0, body_width_mm=5.0, body_height_mm=0.85,
        total_pins=32, pins_lr=8, pins_tb=8,
        lead_pitch_mm=0.50, lead_width_mm=0.25, inner_lead_mm=0.45,
        paddle_length_mm=3.25, paddle_width_mm=3.25,
        thermal_enhanced=True,
        wire_material="gold", wire_diameter_um=25.0,
        max_wire_length_mm=1.701,
        min_wire_gap_um=72.0,
        max_lead_skew_deg=3.5,
        supports_exposed_pad_downbond=False,
        tags=["IHP", "bondplan-validated", "exposed-pad"],
        source_reference="IHP SG13G2 chip_top Bondplan Report / config.yaml",
        source_revision="Bondplan v1.0.0, generated 26 Aug 2026",
        wirebond_provenance="reference",
        max_die_thickness_mm=0.300,
        die_fit_provenance="ASIC prototype packaging rules, QFN limit <300 µm",
    ),

    PackageSpec("QFN-40", "QFN", "JEDEC MO-220",
                "40-lead 6×6 mm QFN, 0.5 mm pitch",
                body_length_mm=6.0, body_width_mm=6.0, body_height_mm=0.9,
                total_pins=40, pins_lr=10, pins_tb=10,
                lead_pitch_mm=0.50, lead_width_mm=0.25, inner_lead_mm=0.45,
                paddle_length_mm=4.20, paddle_width_mm=4.20),

    PackageSpec("QFN-48", "QFN", "JEDEC MO-220",
                "48-lead 7×7 mm QFN, 0.5 mm pitch",
                body_length_mm=7.0, body_width_mm=7.0, body_height_mm=0.9,
                total_pins=48, pins_lr=12, pins_tb=12,
                lead_pitch_mm=0.50, lead_width_mm=0.25, inner_lead_mm=0.45,
                paddle_length_mm=5.10, paddle_width_mm=5.10),

    PackageSpec("QFN-64", "QFN", "JEDEC MO-220",
                "64-lead 9×9 mm QFN, 0.5 mm pitch",
                body_length_mm=9.0, body_width_mm=9.0, body_height_mm=0.9,
                total_pins=64, pins_lr=16, pins_tb=16,
                lead_pitch_mm=0.50, lead_width_mm=0.25, inner_lead_mm=0.45,
                paddle_length_mm=6.50, paddle_width_mm=6.50),

    # MirrorSemi open-cavity QFN series (air-cavity MEMS/RF)
    PackageSpec("M-QFN8W.65",  "QFN", "MirrorSemi",
                "8-lead open-cavity QFN 2×2 mm, 0.65 mm pitch",
                body_length_mm=2.0, body_width_mm=2.0, body_height_mm=0.85,
                total_pins=8, pins_lr=2, pins_tb=2,
                lead_pitch_mm=0.65, lead_width_mm=0.30, inner_lead_mm=0.30,
                paddle_length_mm=1.20, paddle_width_mm=1.20,
                has_die_paddle=True, tags=["open-cavity", "RF", "MEMS"]),

    PackageSpec("M-QFN16W.65", "QFN", "MirrorSemi",
                "16-lead open-cavity QFN 4×4 mm, 0.65 mm pitch",
                body_length_mm=4.0, body_width_mm=4.0, body_height_mm=0.85,
                total_pins=16, pins_lr=4, pins_tb=4,
                lead_pitch_mm=0.65, lead_width_mm=0.30, inner_lead_mm=0.40,
                paddle_length_mm=2.60, paddle_width_mm=2.60,
                has_die_paddle=True, tags=["open-cavity", "RF", "MEMS"]),

    PackageSpec("M-QFN24W.5",  "QFN", "MirrorSemi",
                "24-lead open-cavity QFN 4×4 mm, 0.5 mm pitch",
                body_length_mm=4.0, body_width_mm=4.0, body_height_mm=0.85,
                total_pins=24, pins_lr=6, pins_tb=6,
                lead_pitch_mm=0.50, lead_width_mm=0.25, inner_lead_mm=0.40,
                paddle_length_mm=2.50, paddle_width_mm=2.50,
                has_die_paddle=True, tags=["open-cavity", "RF", "MEMS"]),

    PackageSpec("M-QFN32W.5",  "QFN", "MirrorSemi",
                "32-lead open-cavity QFN 5×5 mm, 0.5 mm pitch",
                body_length_mm=5.0, body_width_mm=5.0, body_height_mm=0.85,
                total_pins=32, pins_lr=8, pins_tb=8,
                lead_pitch_mm=0.50, lead_width_mm=0.25, inner_lead_mm=0.45,
                paddle_length_mm=3.40, paddle_width_mm=3.40,
                has_die_paddle=True, tags=["open-cavity", "RF", "MEMS"]),

    # ══════════════════════════════════════════════════════
    # QFP  (JEDEC MS-026)
    # ══════════════════════════════════════════════════════

    PackageSpec("LQFP-32", "QFP", "JEDEC MS-026 / IPC-7351B",
                "32-lead LQFP 7×7×1.4 mm, 0.8 mm pitch",
                body_length_mm=7.0, body_width_mm=7.0, body_height_mm=1.4,
                total_pins=32, pins_lr=8, pins_tb=8,
                lead_pitch_mm=0.80, lead_width_mm=0.45, inner_lead_mm=1.0,
                outer_lead_mm=0.6,
                paddle_length_mm=3.0, paddle_width_mm=3.0),

    PackageSpec("LQFP-44", "QFP", "JEDEC MS-026",
                "44-lead LQFP 10×10×1.4 mm, 0.8 mm pitch",
                body_length_mm=10.0, body_width_mm=10.0, body_height_mm=1.4,
                total_pins=44, pins_lr=11, pins_tb=11,
                lead_pitch_mm=0.80, lead_width_mm=0.45, inner_lead_mm=1.0,
                outer_lead_mm=0.6,
                paddle_length_mm=5.0, paddle_width_mm=5.0),

    PackageSpec("LQFP-64", "QFP", "JEDEC MS-026",
                "64-lead LQFP 10×10×1.4 mm, 0.5 mm pitch",
                body_length_mm=10.0, body_width_mm=10.0, body_height_mm=1.4,
                total_pins=64, pins_lr=16, pins_tb=16,
                lead_pitch_mm=0.50, lead_width_mm=0.22, inner_lead_mm=1.0,
                outer_lead_mm=0.6,
                paddle_length_mm=5.0, paddle_width_mm=5.0),

    PackageSpec("LQFP-100", "QFP", "JEDEC MS-026",
                "100-lead LQFP 14×14×1.4 mm, 0.5 mm pitch",
                body_length_mm=14.0, body_width_mm=14.0, body_height_mm=1.4,
                total_pins=100, pins_lr=25, pins_tb=25,
                lead_pitch_mm=0.50, lead_width_mm=0.22, inner_lead_mm=1.0,
                outer_lead_mm=0.6,
                paddle_length_mm=8.0, paddle_width_mm=8.0),

    PackageSpec("LQFP-144", "QFP", "JEDEC MS-026",
                "144-lead LQFP 20×20×1.4 mm, 0.5 mm pitch",
                body_length_mm=20.0, body_width_mm=20.0, body_height_mm=1.4,
                total_pins=144, pins_lr=36, pins_tb=36,
                lead_pitch_mm=0.50, lead_width_mm=0.22, inner_lead_mm=1.0,
                outer_lead_mm=0.6,
                paddle_length_mm=12.0, paddle_width_mm=12.0),

    PackageSpec("TQFP-32", "QFP", "JEDEC MS-026",
                "32-lead TQFP 7×7×1.0 mm, 0.8 mm pitch",
                body_length_mm=7.0, body_width_mm=7.0, body_height_mm=1.0,
                total_pins=32, pins_lr=8, pins_tb=8,
                lead_pitch_mm=0.80, lead_width_mm=0.45, inner_lead_mm=1.0,
                outer_lead_mm=0.6,
                paddle_length_mm=3.0, paddle_width_mm=3.0),

    PackageSpec("PQFP-208", "QFP", "JEDEC MS-026",
                "208-lead PQFP 30.6×28.6×3.8 mm, 0.5 mm pitch",
                body_length_mm=30.6, body_width_mm=28.6, body_height_mm=3.8,
                total_pins=208, pins_lr=52, pins_tb=52,
                lead_pitch_mm=0.50, lead_width_mm=0.22, inner_lead_mm=1.5,
                outer_lead_mm=0.8,
                paddle_length_mm=18.0, paddle_width_mm=16.0),

    # ══════════════════════════════════════════════════════
    # DIP  (JEDEC MS-001)   modelled as 2-sided QFP
    # ══════════════════════════════════════════════════════

    PackageSpec("DIP-8",  "DIP", "JEDEC MS-001",
                "8-lead DIP 9.27×6.35×3.3 mm, 2.54 mm pitch",
                body_length_mm=9.27, body_width_mm=6.35, body_height_mm=3.3,
                total_pins=8, pins_lr=4, pins_tb=0,
                lead_pitch_mm=2.54, lead_width_mm=0.50, inner_lead_mm=2.5,
                outer_lead_mm=3.3, has_die_paddle=False),

    PackageSpec("DIP-14", "DIP", "JEDEC MS-001",
                "14-lead DIP 19.05×6.35×3.3 mm, 2.54 mm pitch",
                body_length_mm=19.05, body_width_mm=6.35, body_height_mm=3.3,
                total_pins=14, pins_lr=7, pins_tb=0,
                lead_pitch_mm=2.54, lead_width_mm=0.50, inner_lead_mm=2.5,
                outer_lead_mm=3.3, has_die_paddle=False),

    PackageSpec("DIP-16", "DIP", "JEDEC MS-001",
                "16-lead DIP 19.05×6.35×3.3 mm, 2.54 mm pitch",
                body_length_mm=19.05, body_width_mm=6.35, body_height_mm=3.3,
                total_pins=16, pins_lr=8, pins_tb=0,
                lead_pitch_mm=2.54, lead_width_mm=0.50, inner_lead_mm=2.5,
                outer_lead_mm=3.3, has_die_paddle=False),

    PackageSpec("DIP-28", "DIP", "JEDEC MS-001",
                "28-lead DIP 35.56×7.62×3.3 mm, 2.54 mm pitch",
                body_length_mm=35.56, body_width_mm=7.62, body_height_mm=3.3,
                total_pins=28, pins_lr=14, pins_tb=0,
                lead_pitch_mm=2.54, lead_width_mm=0.50, inner_lead_mm=3.0,
                outer_lead_mm=3.3, has_die_paddle=False),

    PackageSpec("DIP-40", "DIP", "JEDEC MS-001",
                "40-lead DIP 52.07×15.24×3.3 mm, 2.54 mm pitch",
                body_length_mm=52.07, body_width_mm=15.24, body_height_mm=3.3,
                total_pins=40, pins_lr=20, pins_tb=0,
                lead_pitch_mm=2.54, lead_width_mm=0.50, inner_lead_mm=6.0,
                outer_lead_mm=3.3, has_die_paddle=False),

    # ══════════════════════════════════════════════════════
    # SOIC  (JEDEC MS-012)
    # ══════════════════════════════════════════════════════

    PackageSpec("SOIC-8",  "SOIC", "JEDEC MS-012",
                "8-lead SOIC 4.9×3.9×1.75 mm, 1.27 mm pitch",
                body_length_mm=4.9, body_width_mm=3.9, body_height_mm=1.75,
                total_pins=8, pins_lr=4, pins_tb=0,
                lead_pitch_mm=1.27, lead_width_mm=0.42, inner_lead_mm=1.5,
                outer_lead_mm=0.8, has_die_paddle=False),

    PackageSpec("SOIC-14", "SOIC", "JEDEC MS-012",
                "14-lead SOIC 8.65×3.9×1.75 mm, 1.27 mm pitch",
                body_length_mm=8.65, body_width_mm=3.9, body_height_mm=1.75,
                total_pins=14, pins_lr=7, pins_tb=0,
                lead_pitch_mm=1.27, lead_width_mm=0.42, inner_lead_mm=1.5,
                outer_lead_mm=0.8, has_die_paddle=False),

    PackageSpec("SOIC-16", "SOIC", "JEDEC MS-012",
                "16-lead SOIC 9.9×3.9×1.75 mm, 1.27 mm pitch",
                body_length_mm=9.9, body_width_mm=3.9, body_height_mm=1.75,
                total_pins=16, pins_lr=8, pins_tb=0,
                lead_pitch_mm=1.27, lead_width_mm=0.42, inner_lead_mm=1.5,
                outer_lead_mm=0.8, has_die_paddle=False),

    PackageSpec("SOIC-20W", "SOIC", "JEDEC MS-013",
                "20-lead SOIC Wide 12.8×7.5×2.35 mm, 1.27 mm pitch",
                body_length_mm=12.8, body_width_mm=7.5, body_height_mm=2.35,
                total_pins=20, pins_lr=10, pins_tb=0,
                lead_pitch_mm=1.27, lead_width_mm=0.42, inner_lead_mm=2.5,
                outer_lead_mm=0.8, has_die_paddle=False),

    # ══════════════════════════════════════════════════════
    # TSSOP  (JEDEC MO-153)
    # ══════════════════════════════════════════════════════

    PackageSpec("TSSOP-8",  "TSSOP", "JEDEC MO-153",
                "8-lead TSSOP 3.0×4.4×1.2 mm, 0.65 mm pitch",
                body_length_mm=3.0, body_width_mm=4.4, body_height_mm=1.2,
                total_pins=8, pins_lr=4, pins_tb=0,
                lead_pitch_mm=0.65, lead_width_mm=0.30, inner_lead_mm=0.8,
                outer_lead_mm=0.5, has_die_paddle=False),

    PackageSpec("TSSOP-16", "TSSOP", "JEDEC MO-153",
                "16-lead TSSOP 5.0×4.4×1.2 mm, 0.65 mm pitch",
                body_length_mm=5.0, body_width_mm=4.4, body_height_mm=1.2,
                total_pins=16, pins_lr=8, pins_tb=0,
                lead_pitch_mm=0.65, lead_width_mm=0.30, inner_lead_mm=0.8,
                outer_lead_mm=0.5, has_die_paddle=False),

    PackageSpec("TSSOP-20", "TSSOP", "JEDEC MO-153",
                "20-lead TSSOP 6.5×4.4×1.2 mm, 0.65 mm pitch",
                body_length_mm=6.5, body_width_mm=4.4, body_height_mm=1.2,
                total_pins=20, pins_lr=10, pins_tb=0,
                lead_pitch_mm=0.65, lead_width_mm=0.30, inner_lead_mm=0.8,
                outer_lead_mm=0.5, has_die_paddle=False),

    PackageSpec("TSSOP-28", "TSSOP", "JEDEC MO-153",
                "28-lead TSSOP 9.7×4.4×1.2 mm, 0.65 mm pitch",
                body_length_mm=9.7, body_width_mm=4.4, body_height_mm=1.2,
                total_pins=28, pins_lr=14, pins_tb=0,
                lead_pitch_mm=0.65, lead_width_mm=0.30, inner_lead_mm=0.8,
                outer_lead_mm=0.5, has_die_paddle=False),

    # ══════════════════════════════════════════════════════
    # BGA  (JEDEC MS-034)
    # ══════════════════════════════════════════════════════

    PackageSpec("BGA-64",   "BGA", "JEDEC MS-034",
                "64-ball BGA 8×8 mm, 1.0 mm pitch, ⌀0.6 mm balls",
                body_length_mm=8.0,  body_width_mm=8.0,  body_height_mm=1.2,
                total_pins=64,
                bga_ball_dia_mm=0.60, bga_ball_pitch_mm=1.00),

    PackageSpec("BGA-100",  "BGA", "JEDEC MS-034",
                "100-ball BGA 10×10 mm, 1.0 mm pitch, ⌀0.6 mm balls",
                body_length_mm=10.0, body_width_mm=10.0, body_height_mm=1.2,
                total_pins=100,
                bga_ball_dia_mm=0.60, bga_ball_pitch_mm=1.00),

    PackageSpec("BGA-144",  "BGA", "JEDEC MS-034",
                "144-ball BGA 13×13 mm, 1.0 mm pitch, ⌀0.6 mm balls",
                body_length_mm=13.0, body_width_mm=13.0, body_height_mm=1.2,
                total_pins=144,
                bga_ball_dia_mm=0.60, bga_ball_pitch_mm=1.00),

    PackageSpec("BGA-256",  "BGA", "JEDEC MS-034",
                "256-ball BGA 17×17 mm, 1.0 mm pitch, ⌀0.6 mm balls",
                body_length_mm=17.0, body_width_mm=17.0, body_height_mm=1.2,
                total_pins=256,
                bga_ball_dia_mm=0.60, bga_ball_pitch_mm=1.00),

    PackageSpec("BGA-324",  "BGA", "JEDEC MS-034",
                "324-ball BGA 19×19 mm, 1.0 mm pitch, ⌀0.6 mm balls",
                body_length_mm=19.0, body_width_mm=19.0, body_height_mm=1.4,
                total_pins=324,
                bga_ball_dia_mm=0.60, bga_ball_pitch_mm=1.00),

    PackageSpec("FBGA-165", "BGA", "JEDEC MS-034",
                "165-ball Fine-pitch BGA 11×13 mm, 0.8 mm pitch, ⌀0.45 mm balls",
                body_length_mm=11.0, body_width_mm=13.0, body_height_mm=1.0,
                total_pins=165,
                bga_ball_dia_mm=0.45, bga_ball_pitch_mm=0.80),

    PackageSpec("WLCSP-25", "BGA", "JEDEC WLCSP",
                "25-ball Wafer-Level CSP 1.665×1.665 mm, 0.4 mm pitch, ⌀0.27 mm balls",
                body_length_mm=1.665, body_width_mm=1.665, body_height_mm=0.6,
                total_pins=25,
                bga_ball_dia_mm=0.27, bga_ball_pitch_mm=0.40,
                tags=["WLCSP"]),

    PackageSpec("WLCSP-49", "BGA", "JEDEC WLCSP",
                "49-ball WLCSP 2.315×2.315 mm, 0.4 mm pitch, ⌀0.27 mm balls",
                body_length_mm=2.315, body_width_mm=2.315, body_height_mm=0.6,
                total_pins=49,
                bga_ball_dia_mm=0.27, bga_ball_pitch_mm=0.40,
                tags=["WLCSP"]),
]


def refresh_ihp_wirebond_metadata() -> None:
    """Refresh the IHP catalog variant from the optional source package."""
    packaging_dir = os.environ.get("DIPASSIONATE_IHP_PACKAGING")
    if not packaging_dir:
        gds_path = os.environ.get("DIPASSIONATE_IHP_GDS")
        if gds_path:
            packaging_dir = str(Path(gds_path).resolve().parent.parent / "packaging")
    if not packaging_dir:
        return

    root = Path(packaging_dir)
    config_path = root / "config.yaml"
    report_path = root / "result.md"
    if not config_path.is_file() or not report_path.is_file():
        return

    package = next(
        (item for item in ALL_PACKAGES if item.name == "OP-QFN32-A4-FIT-IHP"),
        None,
    )
    if package is None:
        return

    try:
        evidence = extract_ihp_wirebond_requirements(config_path, report_path)
    except (OSError, ValueError):
        package.wirebond_provenance = "reference"
        return

    geometry_path = root / "layout" / "OP_QFN32_A4_FIT.gds"
    geometry_validated = False
    if geometry_path.is_file():
        try:
            try:
                from .IHPPackageGDS import (
                    extract_ihp_package_geometry,
                    validate_bond_mappings,
                )
            except (ImportError, ValueError):
                gds_module_path = Path(__file__).with_name("IHPPackageGDS.py")
                gds_spec = importlib.util.spec_from_file_location(
                    "ihp_package_gds_catalog_source", gds_module_path
                )
                assert gds_spec and gds_spec.loader
                gds_module = importlib.util.module_from_spec(gds_spec)
                sys.modules[gds_spec.name] = gds_module
                gds_spec.loader.exec_module(gds_module)
                extract_ihp_package_geometry = gds_module.extract_ihp_package_geometry
                validate_bond_mappings = gds_module.validate_bond_mappings
            geometry = extract_ihp_package_geometry(geometry_path)
            geometry_validated = validate_bond_mappings(
                geometry, evidence.mappings
            ).is_valid
        except (ImportError, OSError, ValueError):
            geometry_validated = False

    package.wire_material = evidence.wire_material
    package.wire_diameter_um = evidence.wire_diameter_um
    package.max_wire_length_mm = (
        evidence.observed_wire_length_max_um / 1000.0
        if evidence.observed_wire_length_max_um is not None
        else None
    )
    package.min_wire_gap_um = evidence.minimum_wire_gap_um
    package.max_lead_skew_deg = evidence.observed_max_lead_skew_deg
    package.supports_exposed_pad_downbond = (
        evidence.exposed_pad_downbond_count > 0
    )
    package.source_reference = " / ".join(evidence.sources)
    package.source_revision = (
        f"{evidence.design} / {evidence.package_name}; "
        f"{len(evidence.mappings)} pin mappings"
    )
    package.wirebond_provenance = (
        "validated" if geometry_validated else "reference"
    )


refresh_ihp_wirebond_metadata()


# ── search API ─────────────────────────────────────────────────────────────────

def search_packages(query: str,
                    family: Optional[str] = None) -> List[PackageSpec]:
    """
    Search ALL_PACKAGES by name, family, pin count, or description.

    Parameters
    ----------
    query  : free-text search string (case-insensitive)
    family : optional family filter: "QFN" | "QFP" | "DIP" | "SOIC" |
             "TSSOP" | "BGA"

    Returns list sorted by relevance (exact name match first).
    """
    q = query.strip().lower()
    results: List[Tuple[int, PackageSpec]] = []

    for pkg in ALL_PACKAGES:
        if family and pkg.family.upper() != family.upper():
            continue

        score = 0
        name_l = pkg.name.lower()
        desc_l = pkg.description.lower()
        tags_l = " ".join(pkg.tags).lower()

        if q == name_l:
            score = 100
        elif q in name_l:
            score = 80
        elif name_l.startswith(q):
            score = 70
        elif q in desc_l:
            score = 40
        elif q in tags_l:
            score = 30
        elif q in pkg.family.lower():
            score = 20
        elif q in str(pkg.total_pins):
            score = 10

        if score > 0:
            results.append((score, pkg))

    results.sort(key=lambda x: -x[0])
    return [pkg for _, pkg in results]


def compatible_packages(requirements, packages: Optional[List[PackageSpec]] = None,
                        family: Optional[str] = None,
                        constraints: Optional[dict] = None) -> List[PackageSpec]:
    """
    Return package candidates compatible with extracted chip requirements.

    Requirements may be a ``ChipRequirements`` instance or a mapping with the
    same field names. Candidate packages must have matching pad count and
    peripheral side counts, and their body must contain the die footprint.
    """
    candidates = []
    constraints = _constraint_values(constraints)
    max_height_mm = constraints["max_body_height_mm"]
    require_die_paddle = constraints["require_die_paddle"]
    require_open_cavity = constraints["require_open_cavity"]
    source = packages if packages is not None else ALL_PACKAGES
    for package in source:
        if family and package.family.upper() != family.upper():
            continue
        if package.total_pins != _requirement_value(requirements, "pad_count"):
            continue
        side_counts = _requirement_value(requirements, "pads_per_side") or {}
        if side_counts and (
            package.pins_lr != side_counts.get("left", 0)
            or package.pins_lr != side_counts.get("right", 0)
            or package.pins_tb != side_counts.get("top", 0)
            or package.pins_tb != side_counts.get("bottom", 0)
        ):
            continue
        if (
            package.body_length_mm < _requirement_value(requirements, "die_length_mm")
            or package.body_width_mm < _requirement_value(requirements, "die_width_mm")
        ):
            continue
        if max_height_mm is not None and package.body_height_mm > max_height_mm:
            continue
        die_thickness_mm = _requirement_value(
            requirements, "die_thickness_mm"
        )
        die_thickness_source = _requirement_value(
            requirements, "die_thickness_source"
        )
        if (
            die_thickness_mm is not None
            and package.max_die_thickness_mm is not None
            and (
                die_thickness_source is None
                or die_thickness_source
                not in ("unknown", "no_stackup_default")
            )
            and die_thickness_mm >= package.max_die_thickness_mm
        ):
            continue
        die_clearance_x = (
            package.die_clearance_x_mm
            if package.die_clearance_x_mm is not None
            else 0.0
        )
        die_clearance_y = (
            package.die_clearance_y_mm
            if package.die_clearance_y_mm is not None
            else 0.0
        )
        if (
            package.cavity_length_mm is not None
            and package.cavity_width_mm is not None
            and (
                _requirement_value(requirements, "die_length_mm")
                > package.cavity_length_mm - die_clearance_x
                or _requirement_value(requirements, "die_width_mm")
                > package.cavity_width_mm - die_clearance_y
            )
        ):
            continue
        if require_die_paddle and not package.has_die_paddle:
            continue
        if require_open_cavity and "open-cavity" not in package.tags:
            continue
        if not _capability_at_least(
            package.max_power_w, constraints["max_power_w"]
        ):
            continue
        if (
            constraints["max_theta_ja_c_per_w"] is not None
            and (
                package.theta_ja_c_per_w is None
                or package.theta_ja_c_per_w > constraints["max_theta_ja_c_per_w"]
            )
        ):
            continue
        if (
            constraints["required_max_junction_temp_c"] is not None
            and (
                package.max_junction_temp_c is None
                or package.max_junction_temp_c
                < constraints["required_max_junction_temp_c"]
            )
        ):
            continue
        if constraints["require_rf_capable"] and not package.rf_capable:
            continue
        if (
            constraints["rf_frequency_ghz"] is not None
            and (
                not package.rf_capable
                or package.rf_max_frequency_ghz is None
                or package.rf_max_frequency_ghz < constraints["rf_frequency_ghz"]
            )
        ):
            continue
        if constraints["require_exposed_ground"] and not package.exposed_ground:
            continue
        if not _capability_at_least(
            package.max_wire_length_mm, constraints["required_wire_length_mm"]
        ):
            continue
        if (
            constraints["max_wire_length_mm"] is not None
            and (
                package.max_wire_length_mm is None
                or package.max_wire_length_mm < constraints["max_wire_length_mm"]
            )
        ):
            continue
        if (
            constraints["wire_material"] is not None
            and package.wire_material != constraints["wire_material"]
        ):
            continue
        if (
            constraints["wire_diameter_um"] is not None
            and package.wire_diameter_um != constraints["wire_diameter_um"]
        ):
            continue
        if (
            constraints["min_wire_gap_um"] is not None
            and (
                package.min_wire_gap_um is None
                or package.min_wire_gap_um < constraints["min_wire_gap_um"]
            )
        ):
            continue
        if (
            constraints["max_bond_angle_deg"] is not None
            and (
                package.max_bond_angle_deg is None
                or package.max_bond_angle_deg > constraints["max_bond_angle_deg"]
            )
        ):
            continue
        if (
            constraints["max_lead_skew_deg"] is not None
            and (
                package.max_lead_skew_deg is None
                or package.max_lead_skew_deg > constraints["max_lead_skew_deg"]
            )
        ):
            continue
        if constraints["require_hermetic"] and not package.hermetic:
            continue
        candidates.append(package)

    die_area = (
        _requirement_value(requirements, "die_length_mm")
        * _requirement_value(requirements, "die_width_mm")
    )
    candidates.sort(
        key=lambda package: (
            package.body_length_mm * package.body_width_mm - die_area,
            bool(package.tags),
            package.body_height_mm,
            package.name,
        )
    )
    return candidates


def _requirement_value(requirements, name: str):
    if isinstance(requirements, dict):
        return requirements.get(name)
    return getattr(requirements, name)


def _constraint_values(constraints) -> dict:
    """Normalize a dataclass or mapping without silently inventing capability."""
    values = {
        "max_body_height_mm": None,
        "max_die_thickness_mm": None,
        "die_thickness_source": None,
        "require_die_paddle": False,
        "require_open_cavity": False,
        "max_power_w": None,
        "max_theta_ja_c_per_w": None,
        "required_max_junction_temp_c": None,
        "rf_frequency_ghz": None,
        "require_rf_capable": False,
        "require_exposed_ground": False,
        "required_wire_length_mm": None,
        "wire_material": None,
        "wire_diameter_um": None,
        "max_wire_length_mm": None,
        "min_wire_gap_um": None,
        "max_bond_angle_deg": None,
        "max_lead_skew_deg": None,
        "require_hermetic": False,
    }
    if constraints is None:
        return values
    source = constraints if isinstance(constraints, dict) else vars(constraints)
    aliases = {
        "max_height_mm": "max_body_height_mm",
    }
    for name in values:
        if name in source:
            values[name] = source[name]
    for old_name, new_name in aliases.items():
        if old_name in source and values[new_name] is None:
            values[new_name] = source[old_name]
    return values


def _capability_at_least(capability, required) -> bool:
    return required is None or (
        capability is not None and capability >= required
    )


def get_package(name: str) -> Optional[PackageSpec]:
    """Return the first PackageSpec whose name matches exactly (case-insensitive)."""
    n = name.strip().lower()
    for pkg in ALL_PACKAGES:
        if pkg.name.lower() == n:
            return pkg
    return None


def families() -> List[str]:
    """Return sorted list of unique family names in the catalogue."""
    return sorted({p.family for p in ALL_PACKAGES})
