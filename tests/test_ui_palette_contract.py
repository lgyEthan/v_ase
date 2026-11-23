"""Readable complete palettes across actual text and focus surfaces."""
import re
from pathlib import Path


def luminance(color):
    rgb=[int(color[i:i+2],16)/255 for i in (1,3,5)]
    rgb=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
    return sum(a*b for a,b in zip(rgb,[.2126,.7152,.0722]))


def contrast(a,b):
    x,y=sorted([luminance(a),luminance(b)])
    return (y+.05)/(x+.05)


def test_every_palette_keeps_small_text_and_focus_readable():
    css=(Path(__file__).resolve().parents[1]/'v_ase/static/ui_palettes.css').read_text()
    checked=[]
    for selector,block in re.findall(r'([^{}]+)\{([^{}]+)\}',css):
        values=dict(re.findall(r'(--ui-[\w-]+):\s*(#[0-9a-fA-F]{6})',block))
        if '--ui-ink' not in values:continue
        for foreground,background,target in [
            ('ink','field',4.5),('secondary','surface',4.5),('secondary','hover',4.5),
            ('accent','accent-wash',4.5),('on-accent','accent',4.5),('ring','surface',3),
        ]:
            ratio=contrast(values['--ui-'+foreground],values['--ui-'+background])
            assert ratio>=target,(selector.strip(),foreground,background,ratio)
        checked.append(selector)
    assert len(checked)==8


def test_typed_theme_tool_exposes_optional_palette_and_rejects_unknown_values():
    from jsonschema import Draft202012Validator
    from v_ase.ai_tools import tool_catalog
    spec=tool_catalog()['vase_set_interface_theme']
    schema=spec.input_schema
    assert 'palette' not in schema['required']
    assert schema['properties']['palette']['enum']==['graphite','slate','stone','moss']
    validator=Draft202012Validator(schema)
    base={'theme':'dark','expected_document_id':'document','expected_revision':0}
    assert not list(validator.iter_errors(base))
    for palette in ['graphite','slate','stone','moss']:
        assert not list(validator.iter_errors({**base,'palette':palette}))
    assert list(validator.iter_errors({**base,'palette':'unknown'}))
