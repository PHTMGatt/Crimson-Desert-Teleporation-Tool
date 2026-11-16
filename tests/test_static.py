"""Static checks on the injected map JavaScript (no browser is run)."""

import re

import pytest


@pytest.mark.xfail(strict=True,
                   reason="plan #9 / P3: waypoint names are put into the "
                          "map page with innerHTML, so a crafted name runs "
                          "as markup/script. Should use textContent.")
def test_marker_labels_do_not_use_innerhtml_with_names(mod):
    js = mod.MAPGENIE_INJECT_JS
    bad = [m.group(0) for m in re.finditer(r"innerHTML\s*=(?:(?!;[ \t]*\n).)*?wp\.name",
                                           js, re.S)]
    assert not bad
