import hashlib
import io
import json
import logging
import time
import uuid as uuid_lib
import zipfile
from datetime import datetime, timezone

import httpx
import yaml
from .config import settings

log = logging.getLogger("superset")

DASHBOARD_TITLE = "PBM Claims Risk & Compliance Command Center"
DASHBOARD_SLUG = "pbm-claims-command-center"

FILTER_ID = "c0ffee00-0000-4000-8000-000000000001"
FILTER_COLUMN = "company_id"


def _metric(column, aggregate, label, coltype="VARCHAR"):
    return {
        "expressionType": "SIMPLE",
        "column": {"column_name": column, "type": coltype},
        "aggregate": aggregate,
        "label": label,
    }


def _adhoc(column, comparator):
    return {
        "clause": "WHERE",
        "expressionType": "SIMPLE",
        "subject": column,
        "operator": "==",
        "comparator": comparator,
    }


CHART_SPECS = [
    {
        "name": "Total Claims",
        "viz_type": "big_number",
        "params": {
            "metric": _metric("claim_id", "COUNT", "Claims"),
            "granularity_sqla": "claim_date",
            "time_range": "No filter",
        },
    },
    {
        "name": "Anomalies",
        "viz_type": "big_number",
        "params": {
            "metric": _metric("claim_id", "COUNT", "Anomalies"),
            "adhoc_filters": [_adhoc("anomaly", True)],
            "granularity_sqla": "claim_date",
            "time_range": "No filter",
        },
    },
    {
        "name": "Risk Level Distribution",
        "viz_type": "pie",
        "params": {
            "metric": _metric("claim_id", "COUNT", "Claims"),
            "groupby": ["risk_level"],
            "granularity_sqla": "claim_date",
            "time_range": "No filter",
        },
    },
    {
        "name": "Anomalies by Provider",
        "viz_type": "echarts_timeseries_bar",
        "params": {
            "metrics": [_metric("claim_id", "COUNT", "Anomalies")],
            "x_axis": "provider_id",
            "adhoc_filters": [_adhoc("anomaly", True)],
            "granularity_sqla": "claim_date",
            "time_range": "No filter",
        },
    },
    {
        "name": "Claims Trend by Risk Level",
        "viz_type": "echarts_timeseries_line",
        "params": {
            "metrics": [_metric("claim_id", "COUNT", "Claims")],
            "x_axis": "claim_date",
            "groupby": ["risk_level"],
            "granularity_sqla": "claim_date",
            "time_range": "No filter",
        },
    },
    {
        "name": "Top Risk Claims",
        "viz_type": "table",
        "params": {
            "columns": [
                "claim_id", "provider_id", "plan_id", "paid_amount",
                "allowed_amount", "risk_score", "risk_level", "rule_codes",
            ],
            "metrics": [],
            "order_by_cols": ['["risk_score", false]'],
            "row_limit": 50,
            "granularity_sqla": "claim_date",
            "time_range": "No filter",
        },
    },
    {
        "name": "Claim AI Explain",
        "viz_type": "handlebars",
        "params": {
            "columns": ["claim_id", "company_id"],
            "metrics": [],
            "order_by_cols": ['["risk_score", false]'],
            "row_limit": 1,
            "granularity_sqla": "claim_date",
            "time_range": "No filter",
            "handlebars_template": (
                '{{#if data.length}}'
                '<div class="ai-wrap">'
                '<iframe class="ai-frame" '
                'src="%s/explain/view/{{data.0.claim_id}}?company_id={{data.0.company_id}}" '
                'title="AI explanation for claim {{data.0.claim_id}}"></iframe>'
                '</div>'
                '{{else}}'
                '<p class="ai-hint">Select a claim in Top Risk Claims to see its AI explanation.</p>'
                '{{/if}}'
            ) % settings.api_public_url.rstrip("/"),
            "style_template": (
                ".ai-wrap{width:100%;height:100%;min-height:320px}"
                ".ai-frame{width:100%;height:100%;min-height:320px;border:none;"
                "border-radius:8px;background:#0f1420}"
                ".ai-hint{color:#93a1b8;font-size:13px;padding:12px}"
            ),
        },
    },
]


class SupersetClient:
    def __init__(self):
        self.base = settings.superset_url
        self.public = settings.superset_public_url
        self.token = None
        self.csrf = None
        self._dashboard_id = None
        self._dashboard_ready = False
        self._client = httpx.Client(
            base_url=self.base,
            timeout=90,
            headers={"Accept": "application/json"},
        )

    def _headers(self, json_body=False):
        h = {}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if self.csrf:
            h["X-CSRFToken"] = self.csrf
        if json_body:
            h["Content-Type"] = "application/json"
        return h

    def _request(self, method, path, **kwargs):
        json_body = "json" in kwargs
        last = None
        for attempt in range(2):
            try:
                r = self._client.request(
                    method,
                    f"/api/v1/{path}",
                    headers=self._headers(json_body),
                    **kwargs,
                )
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as e:
                last = e
                if e.response.status_code == 401:
                    self.token = None
                    self.csrf = None
                    self.login()
                    continue
                time.sleep(2)
        raise last

    def _request_raw(self, method, path, **kwargs):
        last = None
        for attempt in range(2):
            try:
                r = self._client.request(
                    method,
                    f"/api/v1/{path}",
                    headers=self._headers(),
                    **kwargs,
                )
                r.raise_for_status()
                return r.content
            except httpx.HTTPStatusError as e:
                last = e
                if e.response.status_code == 401:
                    self.token = None
                    self.csrf = None
                    self.login()
                    continue
                time.sleep(2)
        raise last

    def login(self):
        if self.token:
            return
        body = {
            "username": settings.superset_username,
            "password": settings.superset_password,
            "provider": "db",
            "refresh": True,
        }
        r = self._client.post("/api/v1/security/login", json=body)
        r.raise_for_status()
        self.token = r.json()["access_token"]
        try:
            r = self._client.get("/api/v1/security/csrf_token/", headers=self._headers())
            r.raise_for_status()
            self.csrf = r.json()["result"]
        except Exception:
            self.csrf = None

    def _list(self, path):
        return self._request("GET", path).get("result", [])

    def ensure_database(self):
        db_name = "PBM Claims"
        for db in self._list("database/"):
            if db.get("database_name") == db_name:
                return db["id"]
        r = self._request("POST", "database/", json={
            "database_name": db_name,
            "sqlalchemy_uri": settings.database_url.replace("psycopg://", "://", 1),
            "expose_in_sqllab": True,
            "allow_ctas": True,
            "allow_cvas": True,
            "allow_dml": False,
        })
        return r["id"]

    def ensure_dataset(self, db_id):
        for ds in self._list("dataset/"):
            if ds.get("table_name") == "claims" and ds.get("database", {}).get("id") == db_id:
                return ds["id"]
        r = self._request("POST", "dataset/", json={
            "database": db_id,
            "schema": "public",
            "table_name": "claims",
        })
        return r["id"]

    def ensure_charts(self, ds_id):
        existing = {c.get("slice_name"): c for c in self._list("chart/")}
        ids = []
        changed = False
        for spec in CHART_SPECS:
            name = spec["name"]
            params = dict(spec["params"])
            params["datasource"] = f"{ds_id}__table"
            chart = existing.get(name)
            if chart:
                if self._chart_params_differ(chart, params, spec["viz_type"]):
                    try:
                        self._request("PUT", f"chart/{chart['id']}", json={
                            "slice_name": name,
                            "viz_type": spec["viz_type"],
                            "datasource_id": ds_id,
                            "datasource_type": "table",
                            "params": json.dumps(params),
                        })
                        changed = True
                        log.info("updated chart %s (%s)", name, chart["id"])
                    except Exception as e:
                        log.warning("failed to update chart %s: %s", name, e)
                ids.append(chart["id"])
                continue
            try:
                r = self._request("POST", "chart/", json={
                    "datasource_id": ds_id,
                    "datasource_type": "table",
                    "slice_name": name,
                    "viz_type": spec["viz_type"],
                    "params": json.dumps(params),
                })
                ids.append(r["id"])
                changed = True
                log.info("created chart %s (%s)", name, r["id"])
            except Exception as e:
                log.warning("failed to create chart %s: %s", name, e)
        return ids, changed

    @staticmethod
    def _chart_params_differ(chart, expected_params, expected_viz_type):
        if chart.get("viz_type") != expected_viz_type:
            return True
        try:
            current = json.loads(chart.get("params") or "{}")
        except (TypeError, ValueError):
            return True
        for key, value in expected_params.items():
            if current.get(key) != value:
                return True
        return False

    def ensure_dashboard(self, ds_id, chart_ids, sig, force=False):
        if self._dashboard_id is not None and self._dashboard_ready and not force:
            return self._dashboard_id

        dashboard = None
        for d in self._list("dashboard/"):
            if d.get("dashboard_title") == DASHBOARD_TITLE:
                dashboard = d
                break

        if dashboard and not force and dashboard.get("slug") == f"{DASHBOARD_SLUG}-{sig}":
            self._dashboard_id = dashboard["id"]
            self._dashboard_ready = True
            log.info("dashboard up to date (id=%s)", self._dashboard_id)
            return self._dashboard_id

        dash_uuid = None
        if dashboard:
            detail = self._request("GET", f"dashboard/{dashboard['id']}").get("result", {})
            dash_uuid = detail.get("uuid")

        self._dashboard_id = self._import_dashboard(ds_id, chart_ids, dash_uuid, sig)
        self._dashboard_ready = True
        log.info("dashboard ready (id=%s)", self._dashboard_id)
        return self._dashboard_id

    def _import_dashboard(self, ds_id, chart_ids, dash_uuid, sig):
        """Create/update the dashboard via Superset's v1 assets import.

        POST /api/v1/dashboard/ only writes the dashboard row; it never fills
        the dashboard_slices join table that the frontend needs. The import
        endpoint is the only supported path that wires charts + native filters
        into a dashboard (it is what the UI save flow uses).
        """
        q = "!(" + ",".join(str(c) for c in chart_ids) + ")"
        bundle = self._request_raw("GET", f"chart/export/?q={q}")
        name_to_id = dict(zip([s["name"] for s in CHART_SPECS], chart_ids))

        chart_uuid_by_id = {}
        dataset_uuid = None
        chart_files = {}
        dataset_files = []
        database_files = []
        with zipfile.ZipFile(io.BytesIO(bundle)) as zf:
            for name in zf.namelist():
                parts = name.split("/")
                if len(parts) > 1 and parts[0] not in (
                    "charts", "datasets", "databases", "dashboards",
                ):
                    key = "/".join(parts[1:])
                else:
                    key = name
                if not key.endswith(".yaml"):
                    continue
                content = zf.read(name).decode("utf-8")
                if key.startswith("charts/"):
                    cfg = yaml.safe_load(content)
                    chart_files[key] = content
                    if cfg.get("slice_name") in name_to_id:
                        chart_uuid_by_id[name_to_id[cfg["slice_name"]]] = cfg["uuid"]
                elif key.startswith("datasets/"):
                    dataset_files.append((key, content))
                    cfg = yaml.safe_load(content)
                    if dataset_uuid is None:
                        dataset_uuid = cfg.get("uuid")
                elif key.startswith("databases/"):
                    database_files.append((key, content))

        position = self._build_position(chart_ids, chart_uuid_by_id)
        metadata = self._build_metadata(ds_id, dataset_uuid)
        dash_cfg = {
            "dashboard_title": DASHBOARD_TITLE,
            "slug": f"{DASHBOARD_SLUG}-{sig}",
            "uuid": dash_uuid or str(uuid_lib.uuid5(uuid_lib.NAMESPACE_URL, DASHBOARD_TITLE)),
            "position": position,
            "metadata": metadata,
            "version": "1.0.0",
            "published": True,
        }

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Superset's import loader (get_contents_from_bundle -> remove_root)
            # strips the first path component of every entry, so everything
            # must live under a top-level folder.
            prefix = "pbm_assets/"
            zf.writestr(
                prefix + "metadata.yaml",
                yaml.safe_dump(
                    {
                        "version": "1.0.0",
                        "type": "Dashboard",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    sort_keys=False,
                ),
            )
            zf.writestr(
                prefix + "dashboards/PBM_Claims.yaml",
                yaml.safe_dump(dash_cfg, sort_keys=False),
            )
            for key, content in chart_files.items():
                zf.writestr(prefix + key, content)
            for key, content in dataset_files:
                zf.writestr(prefix + key, content)
            for key, content in database_files:
                zf.writestr(prefix + key, content)
        payload = buf.getvalue()

        self._request(
            "POST",
            "dashboard/import/",
            files={"formData": ("pbm_claims_bundle.zip", payload, "application/zip")},
            data={"overwrite": "true"},
        )

        for d in self._list("dashboard/"):
            if d.get("dashboard_title") == DASHBOARD_TITLE:
                return d["id"]
        raise RuntimeError("Dashboard import completed but dashboard was not found")

    @staticmethod
    def _build_position(chart_ids, chart_uuids=None):
        ids = list(chart_ids)
        grid = {"DASHBOARD_VERSION_KEY": "v2"}
        grid["ROOT_ID"] = {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]}
        grid["GRID_ID"] = {"type": "GRID", "id": "GRID_ID", "children": []}
        grid["HEADER_ID"] = {"type": "HEADER", "id": "HEADER_ID", "meta": {"text": DASHBOARD_TITLE}}

        def chart_box(cid, width, height=36):
            meta = {"width": width, "height": height, "chartId": cid}
            if chart_uuids and cid in chart_uuids:
                meta["uuid"] = chart_uuids[cid]
            return {
                "type": "CHART",
                "id": f"CHART-{cid}",
                "children": [],
                "meta": meta,
            }

        rows = [ids[0:2], ids[2:4], ids[4:5], ids[5:7]]
        for ri, chunk in enumerate(rows):
            if not chunk:
                continue
            row_id = f"ROW-{ri}"
            grid[row_id] = {
                "type": "ROW", "id": row_id, "children": [f"CHART-{c}" for c in chunk],
                "meta": {"background": "BACKGROUND_TRANSPARENT"},
            }
            grid["GRID_ID"]["children"].append(row_id)
            for c in chunk:
                width = 6 if len(chunk) > 1 else 12
                grid[f"CHART-{c}"] = chart_box(c, width)
        return grid

    @staticmethod
    def _build_metadata(ds_id=None, ds_uuid=None):
        target = {"column": {"name": FILTER_COLUMN}}
        if ds_uuid:
            target["datasetUuid"] = ds_uuid
        else:
            target["datasetId"] = ds_id
        return {
            "native_filter_configuration": [
                {
                    "id": FILTER_ID,
                    "name": "Company",
                    "filterType": "filter",
                    "targets": [target],
                    "cascadeParentIds": [],
                    "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
                    "controlValues": {},
                    "isActive": True,
                    "allowMultipleSelections": True,
                    "isMandatory": False,
                }
            ],
            "timed_refresh_immune_slices": [],
            "expanded_slices": {},
            "label_colors": {},
            "color_scheme": "superset",
        }

    def dashboard_url(self, company_id=None):
        if not self._dashboard_id:
            raise RuntimeError("Dashboard not provisioned.")
        url = f"{self.public}/superset/dashboard/{self._dashboard_id}/"
        if company_id:
            url += ("?native_filters=(inclusive:!(1),"
                    f"urlParams:!((filters:!((col:{FILTER_COLUMN},opr:IN,value:!({company_id}),gir:!())),scoping:!())))")
        return url


_client = None


def _spec_signature():
    spec = json.dumps({
        "filter": {"id": FILTER_ID, "column": FILTER_COLUMN},
        "charts": [
            {"name": s["name"], "viz_type": s["viz_type"], "params": s["params"]}
            for s in CHART_SPECS
        ],
    }, sort_keys=True, default=str)
    return hashlib.sha256(spec.encode()).hexdigest()[:12]


def get_client():
    global _client
    if _client is None:
        _client = SupersetClient()
    return _client


PROVISION_ATTEMPTS = 12
PROVISION_BACKOFF = 10


def ensure_dashboard():
    client = get_client()
    if client._dashboard_id is not None and client._dashboard_ready:
        return client
    last = None
    for attempt in range(PROVISION_ATTEMPTS):
        try:
            client.login()
            db_id = client.ensure_database()
            ds_id = client.ensure_dataset(db_id)
            chart_ids, changed = client.ensure_charts(ds_id)
            client.ensure_dashboard(ds_id, chart_ids, _spec_signature(), force=changed)
            return client
        except Exception as e:
            last = e
            log.warning("Superset provisioning attempt %s/%s failed: %s",
                        attempt + 1, PROVISION_ATTEMPTS, e)
            if attempt < PROVISION_ATTEMPTS - 1:
                time.sleep(PROVISION_BACKOFF)
    raise last


def dashboard_url(company_id=None):
    return ensure_dashboard().dashboard_url(company_id)
