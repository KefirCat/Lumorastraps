import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Option:
    id: str
    key: str
    flags: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Preset:
    id: str
    kind: str
    options: tuple = ()
    flags: dict = field(default_factory=dict)
    lo: int = 0
    hi: int = 100
    step: int = 1
    default: object = None


def _fps_flags(value):
    if value <= 0:
        return {}
    if value >= 1000:
        return {"DFIntTaskSchedulerTargetFps": 9999}
    return {"DFIntTaskSchedulerTargetFps": max(30, int(value))}


PERFORMANCE = (
    Preset("fps", "slider", lo=0, hi=1000, step=10, default=0),
    Preset("no_shadows", "toggle", flags={"FIntRenderShadowIntensity": 0}, default=False),
    Preset("no_postfx", "toggle", flags={"FFlagDisablePostFx": True}, default=False),
    Preset(
        "no_grass",
        "toggle",
        flags={"FIntFRMMinGrassDistance": 0, "FIntFRMMaxGrassDistance": 0, "FIntRenderGrassDetailStrands": 0},
        default=False,
    ),
)

GRAPHICS = (
    Preset(
        "api",
        "choice",
        options=(
            Option("auto", "o_auto"),
            Option("d3d11", "o_d3d11", {"FFlagDebugGraphicsPreferD3D11": True}),
            Option("vulkan", "o_vulkan", {"FFlagDebugGraphicsPreferVulkan": True}),
            Option("opengl", "o_opengl", {"FFlagDebugGraphicsPreferOpenGL": True}),
        ),
        default="auto",
    ),
    Preset(
        "lighting",
        "choice",
        options=(
            Option("auto", "o_auto"),
            Option("voxel", "o_voxel", {"DFFlagDebugRenderForceTechnologyVoxel": True}),
            Option("shadowmap", "o_shadowmap", {"FFlagDebugForceFutureIsBrightPhase2": True}),
            Option("future", "o_future", {"FFlagDebugForceFutureIsBrightPhase3": True}),
        ),
        default="auto",
    ),
    Preset(
        "msaa",
        "choice",
        options=(
            Option("auto", "o_auto"),
            Option("x1", "o_msaa_off", {"FIntDebugForceMSAASamples": 1}),
            Option("x2", "o_msaa_2", {"FIntDebugForceMSAASamples": 2}),
            Option("x4", "o_msaa_4", {"FIntDebugForceMSAASamples": 4}),
        ),
        default="auto",
    ),
    Preset(
        "texture",
        "choice",
        options=(
            Option("auto", "o_auto"),
            Option("t0", "o_tex_lowest", {"DFFlagTextureQualityOverrideEnabled": True, "DFIntTextureQualityOverride": 0}),
            Option("t1", "o_tex_low", {"DFFlagTextureQualityOverrideEnabled": True, "DFIntTextureQualityOverride": 1}),
            Option("t2", "o_tex_medium", {"DFFlagTextureQualityOverrideEnabled": True, "DFIntTextureQualityOverride": 2}),
            Option("t3", "o_tex_high", {"DFFlagTextureQualityOverrideEnabled": True, "DFIntTextureQualityOverride": 3}),
        ),
        default="auto",
    ),
    Preset("no_dpi", "toggle", flags={"DFFlagDisableDPIScale": True}, default=False),
    Preset("alt_enter", "toggle", flags={"FFlagHandleAltEnterFullscreenManually": False}, default=False),
    Preset("hide_bar", "toggle", flags={"FIntFullscreenTitleBarTriggerDelayMillis": 3600000}, default=False),
)

ALL_PRESETS = PERFORMANCE + GRAPHICS
BY_ID = {p.id: p for p in ALL_PRESETS}

PROFILES = {
    "balanced": {"fps": 144, "no_postfx": False, "api": "d3d11", "msaa": "x2", "texture": "t2"},
    "max_fps": {
        "fps": 1000,
        "no_shadows": True,
        "no_postfx": True,
        "no_grass": True,
        "api": "d3d11",
        "lighting": "voxel",
        "msaa": "x1",
        "texture": "t0",
    },
    "quality": {"fps": 0, "api": "d3d11", "lighting": "future", "msaa": "x4", "texture": "t3"},
    "reset": {},
}


def preset_value(preset: Preset, prefs: dict):
    value = prefs.get(preset.id, preset.default)
    if preset.kind == "choice" and value not in {o.id for o in preset.options}:
        return preset.default
    return value


def preset_flags(preset: Preset, value) -> dict:
    if preset.kind == "choice":
        for option in preset.options:
            if option.id == value:
                return dict(option.flags)
        return {}
    if preset.kind == "toggle":
        return dict(preset.flags) if value else {}
    if preset.id == "fps":
        return _fps_flags(int(value or 0))
    return {}


def build_preset_flags(prefs: dict) -> dict:
    result = {}
    for preset in ALL_PRESETS:
        result.update(preset_flags(preset, preset_value(preset, prefs)))
    return result


def build_flags(prefs: dict, custom: dict) -> dict:
    result = build_preset_flags(prefs)
    for name, value in custom.items():
        result[name] = value
    return result


def profile_prefs(name: str) -> dict:
    values = PROFILES.get(name, {})
    prefs = {}
    for preset in ALL_PRESETS:
        prefs[preset.id] = values.get(preset.id, preset.default)
    return prefs


def parse_value(text: str):
    raw = text.strip()
    low = raw.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    return raw


def format_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def valid_name(name: str) -> bool:
    name = name.strip()
    return bool(name) and len(name) <= 128 and all(c.isalnum() or c in "_." for c in name)


def load_flags_file(path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("not an object")
    clean = {}
    for name, value in data.items():
        if valid_name(str(name)) and isinstance(value, (bool, int, float, str)):
            clean[str(name)] = value
    return clean


def dump_flags(flags: dict) -> str:
    return json.dumps(flags, indent=4, ensure_ascii=False)
