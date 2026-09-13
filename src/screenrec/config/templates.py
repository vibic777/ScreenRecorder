"""Validated overlay templates; filenames are never derived from template names."""
import json
import math
from pathlib import Path

def default_template():
    return {"image": {"enabled": False, "path": "", "x": .72, "y": .06, "w": .22, "h": .22, "opacity": 1.0},
            "text": {"enabled": False, "text": "ScreenRec", "font": "Arial", "size": .055,
                     "color": "#ffffff", "x": .05, "y": .8, "w": .8, "h": .15, "opacity": 1.0}}

def validate(value):
    result = default_template()
    if not isinstance(value, dict):
        return result
    for kind, layer in result.items():
        source = value.get(kind, {})
        if not isinstance(source, dict):
            continue
        for key, default in layer.items():
            item = source.get(key, default)
            if isinstance(default, bool):
                layer[key] = item if type(item) is bool else default
            elif isinstance(default, float):
                if type(item) in (int, float) and math.isfinite(item):
                    layer[key] = max(.005 if key in ("w","h","size") else 0, min(1, item))
            elif isinstance(item, str):
                layer[key] = item[:4000]
        layer["w"] = min(layer["w"], 1-layer["x"])
        layer["h"] = min(layer["h"], 1-layer["y"])
        if layer["w"] < .005 or layer["h"] < .005:
            layer["x"], layer["y"], layer["w"], layer["h"] = 0, 0, .3, .2
    return result

def path():
    from .settings import Settings
    return Settings.path().with_name("templates.json")

def load():
    try:
        data = json.loads(path().read_text(encoding="utf-8"))
        return {name: validate(value) for name, value in data.items() if isinstance(name,str)}
    except (OSError, ValueError, AttributeError):
        return {}

def save(templates):
    destination = path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps({k:validate(v) for k,v in templates.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)
