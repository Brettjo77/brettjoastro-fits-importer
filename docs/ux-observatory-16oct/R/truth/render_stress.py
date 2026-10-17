"""Usage: python3 render_mock.py IN.html OUT.html
Replaces the single token __DATASET__ in IN.html with the JSON of dataset.json,
so a mockup can be written as  <script>const D=__DATASET__;</script>  and
rendered with real data, exactly as the live page is."""
import json, sys
S = "/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/scratchpad/ux2"
src = open(sys.argv[1], encoding="utf-8").read()
assert src.count("__DATASET__") == 1, "the mockup must contain __DATASET__ exactly once"
js = json.dumps(json.load(open("/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/scratchpad/ux2/R/truth/stress-dataset.json"))).replace("</", "<\\/")
open(sys.argv[2], "w", encoding="utf-8").write(src.replace("__DATASET__", js))
print("rendered", sys.argv[2])
