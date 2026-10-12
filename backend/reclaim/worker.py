import logging
import time
from .schemas import now
from .service import ACTIVE, event
from .solver import timestamp

logger=logging.getLogger("reclaim.worker")


def tick(service):
    store=service.store
    # Expiry is a durable timed outbox job, independent of browsers and session TTL.
    # No full-workspace polling or rewriting of inactive photo aggregates.
    job=store.claim_job()
    if not job:
        return False
    try:
        error=service.process(job["workspace_id"],job["entity_id"])
    except Exception:
        logger.exception("Worker could not complete job %s",job["id"])
        error="Worker interrupted. Retry with the same stored payment operation."
    if error and job["attempts"]>=8:
        with store.transaction(job["workspace_id"],check_expiry=False) as (state,db):
            deal=next(d for d in state["deals"] if d["id"]==job["entity_id"])
            deal["status"]="RECOVERY_REQUIRED"
            deal["recovery_note"]=error
            event(state,"system","Operator recovery required","Automatic retries exhausted; inventory stays reserved. Inspect provider outcomes and retry recovery.",deal["id"])
    store.finish_job(job["id"],error,job["generation"])
    return True


def run(service,stop):
    while not stop.is_set():
        try:
            tick(service)
        except Exception:
            logger.exception("Worker polling failed; durable jobs remain queued")
        stop.wait(1)


if __name__=="__main__":
    import threading
    from .config import Settings
    from .repository import Store
    from .service import Service
    config=Settings()
    run(Service(Store(config.database_url),config),threading.Event())
