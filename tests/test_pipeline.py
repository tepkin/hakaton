import json, os, pathlib, sys, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ezdxf
from app import config as cfgmod
from app.core import pipeline
from examples.make_sample_dxf import create_sample_dxf

def test_end_to_end():
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "in.dxf")
    create_sample_dxf(src)
    out = os.path.join(tmp, "out")
    cfg = cfgmod.default_config()
    s = pipeline.run([src], cfg, out)
    assert os.path.exists(os.path.join(out, "result.dxf"))
    doc = ezdxf.readfile(os.path.join(out, "result.dxf"))
    assert cfg["layers"]["trees"] in doc.layers
    assert cfg["layers"]["shrubs"] in doc.layers
    interp = json.load(open(os.path.join(out, "interpretation.json"), encoding="utf-8"))
    approved = [p for p in interp if p["status"] == "approved"]
    assert approved
    for p in approved:
        assert p["checks"] and all(c["npa"] for c in p["checks"])