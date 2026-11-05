"""flow-top's constants for completed tasks are not evidence."""
from pitwall import participation as P


def _view(**files):
    return P.ReceiptView(files=files)


def test_flow_constants_do_not_become_passed_or_pending():
    v = _view()
    assert P.derive_checks(v, True).state == "unknown"
    assert P.derive_review(v, "review pending").state == "unknown"


def test_not_used_label_does_not_leak_into_delivery():
    d = P.derive_delivery(_view(), "unused", "not used by this job")
    assert d.state == "unknown" and "not used" not in d.label


def test_delivered_needs_a_receipt():
    assert P.derive_delivery(_view(), "delivered", "delivered").state == "unknown"
