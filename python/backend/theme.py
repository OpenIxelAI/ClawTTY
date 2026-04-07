"""
theme.py — ClawTTY v3 visual identity system.

Design language: "Lunar Interface"
Inspired by IxelOS palette. Not Mac, not Windows, not Linux. ClawTTY.

Principle: Calm confidence. Every element earns its space.
"""
from __future__ import annotations
import customtkinter as ctk

# ── Palettes ──────────────────────────────────────────────────────────────────
# "Lunar Interface" — deep space tones with celestial accents

DARK: dict[str, str] = {
    # Surfaces — layered depth
    "bg":        "#070b14",   # deep space — the void
    "bg2":       "#0a1020",   # slightly lifted — for subtle contrast areas
    "card":      "#0d1b2a",   # navy depth — primary card surface
    "card2":     "#141e30",   # midnight — elevated cards, hover states
    "card3":     "#1a2540",   # raised — active/selected surfaces

    # Borders & dividers
    "border":    "#1c2940",   # steel — subtle structure
    "border2":   "#243352",   # brighter border for focused/active elements
    "divider":   "#141e30",   # near-invisible separation

    # Text hierarchy
    "text":      "#c8d8e8",   # moonstone — primary readable text
    "text2":     "#e8edf3",   # frost — high-emphasis, headings
    "dim":       "#7e93ab",   # muted — secondary info, timestamps (brightened for readability)
    "faint":     "#4a6280",   # ghost — placeholder, disabled (brightened slightly)

    # Interactive — the life in the interface
    "accent":    "#7eb8d4",   # lunar blue — buttons, links, focus
    "accent2":   "#9b7fc7",   # violet glow — secondary accent, active states
    "gold":      "#d4af37",   # gold — brand mark, premium accent, warnings

    # Semantic
    "red":       "#e05252",   # ember — danger, destructive
    "green":     "#4ade80",   # success — connected, positive
    "yellow":    "#e3b341",   # caution — warnings, pending

    # Interaction states
    "hover":     "#141e30",   # card lift
    "active":    "#1a2540",   # pressed/selected
    "focus":     "#7eb8d420", # lunar blue glow (with alpha for glow effects)
    "glow":      "#9b7fc715", # violet glow (subtle)
}

LIGHT: dict[str, str] = {
    # Surfaces — clean and airy
    "bg":        "#f4f6f9",   # cloud
    "bg2":       "#eef1f5",   # slightly cooler
    "card":      "#ffffff",   # white
    "card2":     "#f0f3f7",   # mist
    "card3":     "#e8ecf2",   # selected surface

    # Borders & dividers
    "border":    "#d0d5dd",   # silver
    "border2":   "#b8bfcc",   # focused border
    "divider":   "#e4e8ee",   # whisper

    # Text hierarchy
    "text":      "#1a1f2e",   # ink — primary
    "text2":     "#0d1220",   # deep ink — headings
    "dim":       "#6b7580",   # secondary
    "faint":     "#9ca3af",   # placeholder

    # Interactive
    "accent":    "#2563a8",   # ocean — buttons, links
    "accent2":   "#7c5fb0",   # violet
    "gold":      "#b8941f",   # amber brand

    # Semantic
    "red":       "#dc2626",   # danger
    "green":     "#16a34a",   # success
    "yellow":    "#ca8a04",   # caution

    # Interaction states
    "hover":     "#e8ecf2",
    "active":    "#dde2ea",
    "focus":     "#2563a820",
    "glow":      "#7c5fb015",
}

_current: dict[str, str] = dict(DARK)
_mode: str = "dark"


def set_mode(mode: str) -> None:
    global _current, _mode
    _mode = mode.lower()
    _current.clear()
    _current.update(DARK if _mode == "dark" else LIGHT)
    ctk.set_appearance_mode("dark" if _mode == "dark" else "light")


def toggle() -> str:
    new = "light" if _mode == "dark" else "dark"
    set_mode(new)
    return new


def is_dark() -> bool:
    return _mode == "dark"


def C(key: str) -> str:
    """Get a color from the current palette. Falls back to magenta for missing keys."""
    return _current.get(key, "#ff00ff")


# ── Typography ────────────────────────────────────────────────────────────────
#
# System: Inter (UI) + JetBrains Mono (code/data)
# Personality comes from weight + spacing, not custom fonts.
#
# Size scale (1440p base, scaling applied on top):
#   Display:  32  — hero moments, empty states
#   Title:    24  — window title, major headers
#   Header:   20  — section headers, dialog titles
#   Body:     16  — primary content
#   Label:    14  — form labels, secondary text
#   Small:    13  — metadata, hints
#   Micro:    12  — badges, timestamps
#   Code:     14  — monospace content

_UI_FAMILY   = "Inter"
_CODE_FAMILY = "JetBrains Mono"


def F(size: int, weight: str = "normal", mono: bool = False) -> ctk.CTkFont:
    """Create a font. Use mono=True for code/data contexts."""
    family = _CODE_FAMILY if mono else _UI_FAMILY
    return ctk.CTkFont(family=family, size=size, weight=weight)


# ── Named presets ─────────────────────────────────────────────────────────────
# These define the typographic hierarchy. Consistent use = professional feel.

def display_font() -> ctk.CTkFont:
    """32pt bold — hero text, empty states, splash moments."""
    return F(32, "bold")

def title_font() -> ctk.CTkFont:
    """24pt bold — window title, page headers."""
    return F(24, "bold")

def header_font() -> ctk.CTkFont:
    """20pt bold — section headers, dialog titles."""
    return F(20, "bold")

def body_font() -> ctk.CTkFont:
    """16pt normal — primary readable content."""
    return F(16)

def body_bold() -> ctk.CTkFont:
    """16pt bold — emphasized body text."""
    return F(16, "bold")

def label_font() -> ctk.CTkFont:
    """14pt normal — form labels, secondary text, buttons."""
    return F(14)

def label_bold() -> ctk.CTkFont:
    """14pt bold — section labels, button text."""
    return F(14, "bold")

def small_font() -> ctk.CTkFont:
    """13pt normal — metadata, hints, helper text."""
    return F(13)

def micro_font() -> ctk.CTkFont:
    """12pt normal — badges, timestamps, fine print."""
    return F(12)

def code_font(size: int = 14) -> ctk.CTkFont:
    """Monospace at given size — code, data, commands."""
    return F(size, mono=True)

def dim_font() -> ctk.CTkFont:
    """13pt normal — same as small, kept for backward compat."""
    return F(13)


# ── Spacing constants ─────────────────────────────────────────────────────────
# Consistent spacing = visual rhythm. Use these, not magic numbers.

PAD_XS  = 4
PAD_SM  = 8
PAD_MD  = 12
PAD_LG  = 16
PAD_XL  = 24
PAD_2XL = 32

RADIUS_SM = 6
RADIUS_MD = 10
RADIUS_LG = 14
RADIUS_XL = 18
