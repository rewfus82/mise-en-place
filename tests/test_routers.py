"""Integration tests for the FastAPI routers (profile, weight_log, diagnostics)."""


class TestProfileRouter:
    def test_get_creates_default_profile(self, client):
        r = client.get("/profile")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == 1
        assert body["goal"] == "maintain"
        assert body["dietary_restrictions"] == []

    def test_dietary_restrictions_round_trip(self, client):
        r = client.put("/profile", json={"dietary_restrictions": ["vegan", "gluten-free"]})
        assert r.status_code == 200
        assert r.json()["dietary_restrictions"] == ["vegan", "gluten-free"]

    def test_body_metrics_trigger_tdee_calc(self, client):
        r = client.put("/profile", json={
            "weight_kg": 80, "height_cm": 180, "age": 30,
            "sex": "male", "activity_level": "moderately_active", "goal": "maintain",
        })
        body = r.json()
        assert body["tdee_calculated"] == 2759
        assert body["calorie_target"] == 2759  # maintain == TDEE

    def test_goal_change_recalculates_targets(self, client):
        client.put("/profile", json={
            "weight_kg": 80, "height_cm": 180, "age": 30,
            "sex": "male", "activity_level": "moderately_active", "goal": "maintain",
        })
        maintain_cal = client.get("/profile").json()["calorie_target"]

        r = client.put("/profile", json={"goal": "bulk"})
        bulk_cal = r.json()["calorie_target"]

        assert bulk_cal > maintain_cal       # bulk adds a surplus
        assert bulk_cal == round(2759 * 1.15)

    def test_tdee_override_bypasses_formula(self, client):
        r = client.put("/profile", json={
            "weight_kg": 80, "height_cm": 180, "age": 30,
            "sex": "male", "activity_level": "moderately_active",
            "tdee_override": 3000,
        })
        assert r.json()["tdee_calculated"] == 3000

    def test_partial_metrics_dont_crash(self, client):
        # Missing height/age — should not attempt TDEE calc, should not error.
        r = client.put("/profile", json={"weight_kg": 80})
        assert r.status_code == 200
        assert r.json()["weight_kg"] == 80


class TestWeightLogRouter:
    def test_upsert_and_list(self, client):
        client.post("/weight-log", json={"date": "2026-06-01", "weight_kg": 80.5})
        client.post("/weight-log", json={"date": "2026-06-02", "weight_kg": 80.2})
        rows = client.get("/weight-log").json()
        assert len(rows) == 2
        assert rows[0]["date"] == "2026-06-02"  # DESC order

    def test_upsert_replaces_same_date(self, client):
        client.post("/weight-log", json={"date": "2026-06-01", "weight_kg": 80.0})
        client.post("/weight-log", json={"date": "2026-06-01", "weight_kg": 79.0})
        rows = client.get("/weight-log").json()
        assert len(rows) == 1
        assert rows[0]["weight_kg"] == 79.0

    def test_delete(self, client):
        client.post("/weight-log", json={"date": "2026-06-01", "weight_kg": 80.0})
        r = client.delete("/weight-log/2026-06-01")
        assert r.status_code == 204
        assert client.get("/weight-log").json() == []


class TestMeasuredTdee:
    def test_returns_none_with_fewer_than_two_weighins(self, client):
        client.post("/weight-log", json={"date": "2026-06-01", "weight_kg": 80.0})
        assert client.get("/weight-log/measured-tdee").json() is None

    def test_returns_none_when_window_under_7_days(self, client):
        client.post("/weight-log", json={"date": "2026-06-01", "weight_kg": 80.0})
        client.post("/weight-log", json={"date": "2026-06-05", "weight_kg": 79.5})
        assert client.get("/weight-log/measured-tdee").json() is None

    def test_returns_none_with_under_7_tracked_days(self, client, seed_eaten_day):
        client.post("/weight-log", json={"date": "2026-06-01", "weight_kg": 80.0})
        client.post("/weight-log", json={"date": "2026-06-15", "weight_kg": 79.0})
        # Only 3 tracked days — below the 7-day minimum.
        for i in range(3):
            seed_eaten_day(f"2026-06-{2 + i:02d}", 2000.0)
        assert client.get("/weight-log/measured-tdee").json() is None

    def test_computes_measured_tdee(self, client, seed_eaten_day):
        # 80 -> 79 kg over 14 days; 7 tracked days @ 2000 kcal.
        client.post("/weight-log", json={"date": "2026-06-01", "weight_kg": 80.0})
        client.post("/weight-log", json={"date": "2026-06-15", "weight_kg": 79.0})
        for i in range(7):
            seed_eaten_day(f"2026-06-{2 + i:02d}", 2000.0)

        body = client.get("/weight-log/measured-tdee").json()
        assert body is not None
        # avg=2000, weight_change=-1kg, days=14 -> 2000 - (-1*7700/14) = 2550
        assert body["measured_tdee"] == 2550
        assert body["window_days"] == 14
        assert body["tracked_days"] == 7
        assert body["avg_daily_calories"] == 2000


class TestDiagnostics:
    def test_health_ok(self, client):
        assert client.get("/health").json() == {"status": "ok"}

    def test_detailed_reports_subsystems(self, client):
        body = client.get("/health/detailed").json()
        assert body["status"] in {"ok", "degraded"}
        assert body["langgraph_version"]
        for key in ("database", "checkpoints", "graph", "anthropic_api_key"):
            assert key in body["checks"]
            assert body["checks"][key]["status"] in {"ok", "error"}
        # The graph must always compile regardless of data-file state.
        assert body["checks"]["graph"]["status"] == "ok"
