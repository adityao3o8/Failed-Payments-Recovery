import secrets
from datetime import datetime

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import Workspace, get_db

DEFAULT_WORKSPACE_SLUG = "acme-saas"


def get_or_create_default_workspace(db: Session) -> Workspace:
    workspace = db.query(Workspace).filter(Workspace.slug == DEFAULT_WORKSPACE_SLUG).first()
    if workspace:
        return workspace

    workspace = Workspace(
        name="Acme SaaS",
        slug=DEFAULT_WORKSPACE_SLUG,
        stripe_connected=True,
        stripe_account_id="acct_demo_1N2x3Y4z",
        api_key=f"rcv_live_{secrets.token_hex(16)}",
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


def get_current_workspace(
    db: Session = Depends(get_db),
    x_workspace_id: int | None = Header(default=None, alias="X-Workspace-Id"),
) -> Workspace:
    if x_workspace_id:
        workspace = db.query(Workspace).filter(Workspace.id == x_workspace_id).first()
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return workspace
    return get_or_create_default_workspace(db)


def log_activity(
    db: Session,
    workspace_id: int,
    event_type: str,
    title: str,
    detail: str | None = None,
    payment_id: int | None = None,
) -> None:
    from app.database import ActivityEvent

    db.add(
        ActivityEvent(
            workspace_id=workspace_id,
            event_type=event_type,
            title=title,
            detail=detail,
            payment_id=payment_id,
            created_at=datetime.utcnow(),
        )
    )
