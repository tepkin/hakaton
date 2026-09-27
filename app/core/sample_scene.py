"""Синтетическая сцена для демо и тестов: граница, здания, дорога, сеть, деревья."""
from __future__ import annotations
import ezdxf


def create_sample_dxf(path: str) -> str:
    doc = ezdxf.new(dxfversion="R2013")
    msp = doc.modelspace()
    for name, color in (("BOUNDARY", 7), ("BUILDINGS", 5), ("ROADS", 8),
                        ("WATER_PIPE", 1), ("TREES_EXIST", 3)):
        doc.layers.add(name, color=color)
    msp.add_lwpolyline([(0, 0), (100, 0), (100, 60), (0, 60)], close=True, dxfattribs={"layer": "BOUNDARY"})
    msp.add_lwpolyline([(10, 10), (30, 10), (30, 25), (10, 25)], close=True, dxfattribs={"layer": "BUILDINGS"})
    msp.add_lwpolyline([(60, 40), (85, 40), (85, 55), (60, 55)], close=True, dxfattribs={"layer": "BUILDINGS"})
    msp.add_lwpolyline([(0, 30), (100, 30), (100, 36), (0, 36)], close=True, dxfattribs={"layer": "ROADS"})
    msp.add_line((0, 45), (100, 48), dxfattribs={"layer": "WATER_PIPE"})
    for x, y in ((50, 20), (60, 22)):
        msp.add_circle((x, y), 2.0, dxfattribs={"layer": "TREES_EXIST"})
    doc.saveas(path)
    return path