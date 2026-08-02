from app.inference.conditions import CONDITIONS, HEALTHY_CLASS


def test_conditions_endpoint_lists_every_class(client):
    response = client.get("/api/conditions")

    assert response.status_code == 200
    body = response.json()
    assert [item["key"] for item in body] == [c.key for c in CONDITIONS]
    assert {"healthy", "yellow", "dead", "small"} == {item["key"] for item in body}


def test_every_condition_carries_an_interpretation_and_an_action(client):
    for item in client.get("/api/conditions").json():
        assert item["label"] and item["appearance"]
        assert item["interpretation"] and item["action"]


def test_healthy_condition_asks_for_no_action(client):
    body = {item["key"]: item for item in client.get("/api/conditions").json()}

    assert body[HEALTHY_CLASS]["action"] == "Tidak ada tindakan"
