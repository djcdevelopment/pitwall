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


# Broker identity and discovery failure.
from pitwall.endpoint_services import build as build_rows  # noqa: E402

IDENTITY = {
    "brokers": [
        {"id": "bh2_broker", "name": "BH2 broker :5672", "responsibility": "", "container": "a", "host": "127.0.0.1", "port": 5672,
         "network_endpoint": "a:5672", "config_path": "", "runtime_note": "", "identity_basis": "x"},
        {"id": "washplant_broker", "name": "Washplant broker :5673", "responsibility": "", "container": "b", "host": "127.0.0.1", "port": 5673,
         "network_endpoint": "b:5672", "config_path": "", "runtime_note": "", "identity_basis": "y"},
    ],
    "explorer": {"container": "c", "ui_url": "http://127.0.0.1:18080/", "queues_url": "u", "attached_broker": "bh2_broker"},
    "aspire": {"container": "d", "ui_host": "127.0.0.1", "ui_port": 18888, "ui_url": "http://127.0.0.1:18888", "otlp": [{"label": "HTTP", "port": 4318}]},
}


def _obs(api):
    return {"brokers": {"bh2_broker": {"tcp": "refused", "container": {"status": "exited", "exit_code": "255", "finished_at": "t"}},
                        "washplant_broker": {"tcp": "open", "container": {"status": "running"}}},
            "explorer_ui": {"status": 200}, "explorer_api": api, "explorer_container": {"status": "running"},
            "aspire_ui": "refused", "aspire_otlp": {"HTTP": "refused"}, "aspire_container": {"status": "exited", "exit_code": "255", "finished_at": "t"}}


def _rows(api):
    rows, notes = build_rows(IDENTITY, _obs(api), "now", "now", 1.0)
    return {r.id: r for r in rows}, notes


def test_brokers_stay_separate_and_a_live_washplant_does_not_cover_bh2():
    r, _ = _rows({"status": 500, "seconds": 5.4})
    assert r["bh2_broker"].state == "unreachable" and "5672" in r["bh2_broker"].detail
    assert r["washplant_broker"].state == "reachable" and r["washplant_broker"].backlog is None


def test_failed_discovery_is_unknown_backlog_not_zero():
    r, _ = _rows({"status": 500, "seconds": 5.4})
    assert r["explorer_api"].backlog.value is None and r["explorer_api"].backlog.status == "unknown" and r["explorer_api"].state == "unreachable"
    r2, _ = _rows({"status": 200, "seconds": 0.1, "json": [{"activeMessageCount": 0}]})
    assert r2["explorer_api"].backlog.value == 0 and r2["explorer_api"].backlog.status == "ok"
    r3, _ = _rows({"status": 200, "seconds": 0.1, "json": [{"name": "q"}]})
    assert r3["explorer_api"].backlog.value is None


def test_explorer_link_stays_enabled_with_backend_annotation():
    r, notes = _rows({"status": 500, "seconds": 5.4})
    link = r["explorer_ui"].link
    assert r["explorer_ui"].state == "reachable" and link.enabled and "backend error" in link.annotation
    assert notes["service_bus"][0] == "reachable" and "backend error" in notes["service_bus"][1]


def test_aspire_ui_and_receiver_are_separate_rows():
    r, _ = _rows({"status": 500, "seconds": 5.4})
    assert r["aspire_ui"].state == "unreachable" and r["aspire_otlp"].state == "unreachable" and r["aspire_ui"].link.enabled is False
