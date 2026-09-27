import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from shapely.geometry import LineString, Point, Polygon
from app import config as cfgmod
from app.core import norm_engine, gen_engine

def _gen(seed=42):
    cfg = cfgmod.default_config(); cfg["run"]["seed"] = seed
    boundary = Polygon([(0, 0), (100, 0), (100, 60), (0, 60)])
    geom = {"water_pipe": [LineString([(0, 30), (100, 30)])]}
    norms = cfgmod.norms()
    z = norm_engine.build_zones(geom, boundary, norms, cfg)
    return gen_engine.generate(geom, z, boundary, norms, cfg, cfgmod.catalog()), z

def test_reproducibility():
    a, _ = _gen(42); b, _ = _gen(42)
    assert [(p["id"], p["x"], p["y"]) for p in a["plantings"]] == \
           [(p["id"], p["x"], p["y"]) for p in b["plantings"]

def test_only_allowed():
    g, z = _gen(7)
    for p in g["plantings"]:
        if p["type"] == "tree":
            assert z["allowed_trees"].contains(Point(p["x"], p["y"]))
        else:
            assert z["allowed_shrubs"].contains(Point(p["x"], p["y"]))

def test_spacing():
    g, _ = _gen(11)
    trees = [p for p in g["plantings"] if p["type"] == "tree"]
    for i, a in enumerate(trees):
        for b in trees[i + 1:]:
            assert Point(a["x"], a["y"]).distance(Point(b["x"], b["y"])) >= 5.0 - 1e-6