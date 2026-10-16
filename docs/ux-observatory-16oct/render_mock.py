"""Usage: python3 render_mock.py IN.html OUT.html
Replaces the single token __DATASET__ in IN.html with the JSON of dataset.json,
so a mockup can be written as  <script>const D=__DATASET__;</script>  and
rendered with real data, exactly as the live page is."""
import json, sys, os
S = os.path.dirname(os.path.abspath(__file__))
src = open(sys.argv[1], encoding="utf-8").read()
assert src.count("__DATASET__") == 1, "the mockup must contain __DATASET__ exactly once"
js = json.dumps(json.load(open(os.path.join(S, "sample-dataset.json")))).replace("</", "<\\/")
open(sys.argv[2], "w", encoding="utf-8").write(src.replace("__DATASET__", js))
print("rendered", sys.argv[2])
