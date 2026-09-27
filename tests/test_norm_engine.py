import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from shapely.geometry import LineString, Point, Polygon
from app import config as cfgmod
from app.core import norm_engine

def _zones():
    cfg = cfgmod.default_config()
    boundary = Polygon([(0, 0), (100, 0), (100, 60), (0, 60)])
    geom = {"water_pipe": [LineString([(0, 30), (100, 30)])]}
    return geom, boundary, cfgmod.norms(), cfg

def test_setback_policy():
    norms = cfgmod.norms()
    norm = next(n for n in norms["setbacks"] if n["key"] == "water_pipe")
    assert norm_engine.setback_distance(norm, "tree", "max") == 5.0
    assert norm_engine.setback_distance(norm, "tree", "min") == 2.0
    assert norm_engine.setback_distance(norm, "shrub", "max") == 2.0

def test_zones():
    geom, boundary, norms, cfg = _zones()
    z = norm_engine.build_zones(geom, boundary, norms, cfg)
    assert not z["allowed_trees"].contains(Point(50, 32))   # внутри буфера дерева
    assert z["allowed_trees"].contains(Point(50, 40))       # дальше 5 м
    assert z["shrub_only"].contains(Point(50, 33.5))        # только кустарник