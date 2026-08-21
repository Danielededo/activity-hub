"""Assert the rendered chart still says what the chart is meant to say.

`helm lint` checks that the templates render; this checks that what they render
still encodes the decisions — migrations before serving, a liveness probe that
does not depend on the database, secrets kept out of the ConfigMap.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def load(path: Path) -> list[dict]:
    docs = [d for d in yaml.safe_load_all(path.read_text()) if d]
    if not docs:
        raise SystemExit(f"{path} rendered nothing")
    return docs


def by_kind(docs: list[dict], kind: str, name_contains: str = "") -> list[dict]:
    return [
        d
        for d in docs
        if d.get("kind") == kind and name_contains in d.get("metadata", {}).get("name", "")
    ]


def one(docs: list[dict], kind: str, name_contains: str = "") -> dict:
    found = by_kind(docs, kind, name_contains)
    if len(found) != 1:
        raise SystemExit(f"expected exactly one {kind} matching {name_contains!r}, got {len(found)}")
    return found[0]


def check_bundled(docs: list[dict]) -> None:
    api = one(docs, "Deployment", "-api")
    spec = api["spec"]["template"]["spec"]

    inits = spec.get("initContainers") or []
    assert any("alembic" in " ".join(c.get("command", [])) for c in inits), (
        "the API must migrate in an init container, so it never serves against "
        "a schema it has not applied"
    )

    container = spec["containers"][0]
    assert container["command"][0] == "uvicorn", (
        "the app container must serve only; migrating here would race across replicas"
    )
    assert container["readinessProbe"]["httpGet"]["path"] == "/api/health", (
        "readiness must check the database so a pod without one stops taking traffic"
    )
    assert container["livenessProbe"]["httpGet"]["path"] == "/", (
        "liveness must not depend on the database, or a blip restarts healthy pods"
    )

    assert api["spec"]["replicas"] == 1, (
        "more than one replica races on the init-container migration"
    )

    # The database URL is a Secret, never the ConfigMap.
    config = one(docs, "ConfigMap", "-api")
    joined = " ".join(f"{k}={v}" for k, v in config["data"].items()).lower()
    for leak in ("password", "database_url", "postgresql+"):
        assert leak not in joined, f"{leak!r} must not appear in the ConfigMap"

    secret = one(docs, "Secret", "-database")
    url = secret["stringData"]["database-url"]
    assert url.startswith("postgresql+psycopg2://"), url
    assert "-postgresql:5432" in url, f"the URL should point at the bundled service: {url}"

    statefulset = one(docs, "StatefulSet")
    claims = statefulset["spec"].get("volumeClaimTemplates") or []
    assert claims, "persistence is on by default, so a claim template is expected"

    web = one(docs, "Deployment", "-web")
    api_url = next(
        e["value"] for e in web["spec"]["template"]["spec"]["containers"][0]["env"]
        if e["name"] == "API_URL"
    )
    assert api_url.endswith("/api/"), api_url
    assert "-api:8000" in api_url, f"the dashboard should proxy to the API service: {api_url}"


def check_external(docs: list[dict]) -> None:
    assert not by_kind(docs, "StatefulSet"), "no database should be rendered when it is external"
    assert not by_kind(docs, "Secret", "-database"), (
        "the chart must not invent a secret for a database it does not own"
    )
    api = one(docs, "Deployment", "-api")
    env = api["spec"]["template"]["spec"]["containers"][0]["env"]
    ref = next(e["valueFrom"]["secretKeyRef"] for e in env if e["name"] == "DATABASE_URL")
    assert ref["name"] == "my-db", ref


def check_ingress(docs: list[dict]) -> None:
    ingress = one(docs, "Ingress")
    rules = ingress["spec"]["rules"]
    assert len(rules) == 1, "one origin, so one rule: the dashboard proxies /api itself"
    backend = rules[0]["http"]["paths"][0]["backend"]["service"]
    assert backend["name"].endswith("-web"), backend


def main() -> int:
    bundled, external, ingress = (Path(p) for p in sys.argv[1:4])
    check_bundled(load(bundled))
    check_external(load(external))
    check_ingress(load(ingress))
    print("rendered chart matches the decisions it is supposed to encode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
