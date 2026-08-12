"""Accounting router: query, databases, discover, health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Security
from pydantic import BaseModel

import config_loader
from api.dependencies import audit, require_role

router = APIRouter(prefix="/v1/accounting", tags=["Accounting / ERP"])

_accounting_db = None


def init(accounting_db) -> None:  # noqa: ANN001
    global _accounting_db
    _accounting_db = accounting_db


class AccountingQuery(BaseModel):
    query: str
    params: dict | None = None
    database: str | None = None


class AddDatabaseRequest(BaseModel):
    key: str
    name: str
    db_url: str
    discover: bool = True


@router.post("/query", dependencies=[Depends(require_role("admin"))])
async def accounting_query(req: AccountingQuery, role: str = Security(require_role("admin"))):
    """Run a whitelisted read-only accounting query (admin only)."""
    assert _accounting_db
    if req.query not in config_loader.allowed_accounting_queries():
        raise HTTPException(
            status_code=403, detail=f"Query '{req.query}' is not allowed by settings"
        )
    audit(
        "accounting_query",
        role,
        {"query": req.query, "params": req.params, "database": req.database},
    )
    try:
        return _accounting_db.run(req.query, db_name=req.database, **(req.params or {}))
    except (RuntimeError, ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/health", dependencies=[Depends(require_role("admin"))])
async def accounting_health():
    """Test all accounting database connections."""
    assert _accounting_db
    results = []
    for db in _accounting_db.list_databases():
        status = _accounting_db.test_connection(db["key"])
        try:
            schema = _accounting_db.get_schema_info(db["key"])
        except RuntimeError:
            schema = None
        results.append(
            {"key": db["key"], "name": db["name"], "connection": status, "schema": schema}
        )

    default_key = _accounting_db.default_db
    return {
        "databases": results,
        "count": len(results),
        "connection": _accounting_db.test_connection(default_key),
        "schema": _accounting_db.get_schema_info(default_key) if default_key else {},
        "available": _accounting_db.available,
    }


@router.post("/discover", dependencies=[Depends(require_role("admin"))])
async def accounting_discover(db_url: str = "", name: str = ""):
    """Auto-discover table/column mappings from a live database."""
    assert _accounting_db
    from connectors.accounting import SCHEMA_CONFIG_PATH, _save_multi_db_config, discover_schema

    if not db_url:
        dbs = _accounting_db.list_databases()
        if not dbs:
            raise HTTPException(status_code=400, detail="No databases configured. Provide db_url.")
        first = dbs[0]
        schema = _accounting_db._get_schema(first["key"])
        db_url = schema.db_url
        if not db_url:
            raise HTTPException(
                status_code=400, detail=f"Database '{first['key']}' has no db_url set"
            )

    try:
        discovered = discover_schema(db_url)
        discovered.db_url = db_url
        if name:
            discovered.name = name
        dbs = _accounting_db.list_databases()
        target_key = dbs[0]["key"] if dbs else "onyx"
        try:
            existing = _accounting_db._get_schema(target_key)
            discovered.name = existing.name or name or discovered.name
            discovered.db_url = db_url
            _accounting_db._databases[target_key] = discovered
            _save_multi_db_config(_accounting_db._databases)
        except (RuntimeError, ValueError):
            _accounting_db.add_database(target_key, name or "Discovered", db_url, discovered)

        audit(
            "accounting_discover",
            "admin",
            {"tables": len(discovered.tables), "database": target_key},
        )
        return {
            "status": "ok",
            "tables": len(discovered.tables),
            "saved_to": SCHEMA_CONFIG_PATH,
            "database": target_key,
            "schema": {k: v["table"] for k, v in discovered.tables.items()},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/databases", dependencies=[Depends(require_role("admin"))])
async def list_accounting_databases():
    assert _accounting_db
    return _accounting_db.list_databases()


@router.post("/databases", dependencies=[Depends(require_role("admin"))])
async def add_accounting_database(
    req: AddDatabaseRequest, role: str = Security(require_role("admin"))
):
    assert _accounting_db
    from connectors.accounting import discover_schema

    schema = None
    if req.discover:
        try:
            discovered = discover_schema(req.db_url)
            discovered.name = req.name
            discovered.db_url = req.db_url
            schema = discovered
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Schema discovery failed: {e}") from e
    try:
        _accounting_db.add_database(req.key, req.name, req.db_url, schema)
        audit("accounting_add_db", role, {"key": req.key, "name": req.name})
        return {
            "status": "ok",
            "key": req.key,
            "name": req.name,
            "tables": len(schema.tables) if schema else 0,
        }
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/databases/{db_key}", dependencies=[Depends(require_role("admin"))])
async def remove_accounting_database(db_key: str, role: str = Security(require_role("admin"))):
    assert _accounting_db
    if not _accounting_db.remove_database(db_key):
        raise HTTPException(status_code=404, detail=f"Database '{db_key}' not found")
    audit("accounting_remove_db", role, {"key": db_key})
    return {"status": "removed", "key": db_key}
