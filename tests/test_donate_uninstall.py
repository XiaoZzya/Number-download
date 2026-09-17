from pathlib import Path

import pytest

from streamgrab.donate import DONATION_TARGETS, _ascii_qr
from streamgrab.uninstall import _validate_tree


def test_donation_targets_render_as_ascii_qr():
    assert {label for label, _ in DONATION_TARGETS} == {"微信支付", "支付宝"}
    for _, target in DONATION_TARGETS:
        rendered = _ascii_qr(target)
        assert "##" in rendered
        assert len(rendered.splitlines()) > 20


def test_uninstaller_rejects_dangerous_roots():
    for path in (Path("/"), Path.home(), Path("/opt"), Path("/usr"), Path("/home"), Path("/root")):
        with pytest.raises(ValueError):
            _validate_tree(path, label="测试目录")
