"""Создание примера входного DXF: python examples/make_sample_dxf.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf

def create_sample_dxf(path):
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

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_input.dxf")
    create_sample_dxf(out)
    print("Создан:", out)