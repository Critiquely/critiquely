"""FastAPI GitHub webhook with multi-workflow event routing."""

import json
from typing import Set, Optional, List
from contextlib import asynccontextmanager
import time

import httpx
import pika
from fastapi import FastAPI, Header, HTTPException, Request, Depends
from unidiff import PatchSet
import uvicorn
import logging
from pydantic_settings import BaseSettings

from routing import EventRouter, RoutingRule, create_default_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    github_token: str
    rabbitmq_host: str = "github-receiver-rabbitmq"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "critiquely"
    rabbitmq_pass: str = "critiquely123"
    dev_mode: bool = False
    rabbitmq_retry_attempts: int = 3
    rabbitmq_retry_delay: int = 5

    class Config:
        env_file = ".env"


settings = Settings()
connection_pool = None
router: Optional[EventRouter] = None

def create_rabbitmq_connection():
    """Create RabbitMQ connection with retry logic."""
    credentials = pika.PlainCredentials(settings.rabbitmq_user, settings.rabbitmq_pass)
    parameters = pika.ConnectionParameters(
        host=settings.rabbitmq_host,
        port=settings.rabbitmq_port,
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300
    )
    return pika.BlockingConnection(parameters)

def ensure_rabbitmq_connection():
    """Ensure RabbitMQ connection is healthy, reconnect if needed."""
    global connection_pool
    
    if connection_pool and not connection_pool.is_closed:
        try:
            # Test connection health
            connection_pool.process_data_events(time_limit=0)
            return connection_pool
        except Exception:
            logger.warning("RabbitMQ connection unhealthy, closing...")
            try:
                connection_pool.close()
            except:
                pass
            connection_pool = None
    
    # Reconnect with retry logic
    for attempt in range(settings.rabbitmq_retry_attempts):
        try:
            connection_pool = create_rabbitmq_connection()
            channel = connection_pool.channel()
            channel.queue_declare(queue=settings.rabbitmq_queue, durable=True)
            channel.close()
            logger.info(f"Connected to RabbitMQ (attempt {attempt + 1})")
            return connection_pool
        except Exception as e:
            logger.warning(f"RabbitMQ connection attempt {attempt + 1} failed: {e}")
            if attempt < settings.rabbitmq_retry_attempts - 1:
                time.sleep(settings.rabbitmq_retry_delay)
            else:
                logger.error("All RabbitMQ connection attempts failed")
                raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    global router

    # Initialize the event router
    router = create_default_router()
    logger.info(f"Initialized event router with events: {router.registered_events}")

    if not settings.dev_mode:
        try:
            ensure_rabbitmq_connection()
        except Exception as e:
            logger.warning(f"Failed to connect to RabbitMQ: {e}. Running in dev mode.")
            settings.dev_mode = True
    else:
        logger.info("Running in dev mode - messages will be printed instead of queued")
    yield
    if connection_pool:
        connection_pool.close()

app = FastAPI(lifespan=lifespan)

def get_rabbitmq_channel():
    """Get RabbitMQ channel with reconnection logic."""
    if settings.dev_mode:
        return None
    
    try:
        connection = ensure_rabbitmq_connection()
        return connection.channel()
    except Exception as e:
        logger.error(f"Failed to get RabbitMQ channel: {e}")
        return None

def publish_to_queue(
    message: dict, queue_name: str, channel=Depends(get_rabbitmq_channel)
):
    """Publish message to a specific RabbitMQ queue with retry logic.

    Args:
        message: The message to publish.
        queue_name: The target queue name.
        channel: RabbitMQ channel (injected).
    """
    if settings.dev_mode:
        logger.info(
            f"[DEV MODE] Would publish to '{queue_name}': {json.dumps(message, indent=2)}"
        )
        return

    for attempt in range(settings.rabbitmq_retry_attempts):
        try:
            if not channel:
                channel = get_rabbitmq_channel()

            if channel:
                # Ensure queue exists
                channel.queue_declare(queue=queue_name, durable=True)

                channel.basic_publish(
                    exchange="",
                    routing_key=queue_name,
                    body=json.dumps(message),
                    properties=pika.BasicProperties(delivery_mode=2),
                )
                channel.close()
                logger.info(
                    f"Message published to '{queue_name}' (attempt {attempt + 1})"
                )
                return
            else:
                raise Exception("Could not get RabbitMQ channel")

        except Exception as e:
            logger.warning(f"Publish attempt {attempt + 1} failed: {e}")
            if attempt < settings.rabbitmq_retry_attempts - 1:
                time.sleep(settings.rabbitmq_retry_delay)
                channel = None  # Force reconnection
            else:
                logger.error("All publish attempts failed, falling back to dev mode")
                logger.info(
                    f"[FALLBACK] Message that failed to publish: {json.dumps(message, indent=2)}"
                )
                raise HTTPException(
                    status_code=500, detail="Failed to publish message after retries"
                )

def extract_changed_lines(patch_text: str, filename: str) -> Set[int]:
    """Extract changed line numbers from patch text."""
    if not patch_text:
        return set()
    
    synthetic_diff = f"--- a/{filename}\n+++ b/{filename}\n{patch_text}"
    patch = PatchSet.from_string(synthetic_diff)
    
    changed = set()
    for patched_file in patch:
        for hunk in patched_file:
            for line in hunk:
                if line.is_added or line.is_removed:
                    changed.add(line.target_line_no or line.source_line_no)
    return changed

async def get_pr_modified_files(pr_url: str) -> list[dict]:
    """Get modified files for a PR."""
    token = settings.github_token.strip()
    if not token:
        logger.error("❌ GitHub token is missing or empty")
        raise RuntimeError("GitHub token is not set or empty")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{pr_url}/files", headers=headers)
        resp.raise_for_status()
    
    return [
        {
            "filename": file.get("filename"),
            "type": file.get("status"),
            "lines_changed": sorted(extract_changed_lines(file.get("patch", ""), file.get("filename", ""))),
        }
        for file in resp.json()
    ]

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "dev_mode": settings.dev_mode,
        "registered_events": router.registered_events if router else [],
    }


@app.post("/webhook")
async def handle_webhook(
    request: Request,
    x_github_event: str = Header(...),
    channel=Depends(get_rabbitmq_channel),
):
    """Handle GitHub webhook and route to appropriate workflow queues."""
    payload = await request.json()

    # Combine event type with action for full event identification
    action = payload.get("action", "")
    full_event = f"{x_github_event}.{action}" if action else x_github_event

    # Get applicable routes
    routes = router.get_routes(full_event, payload)

    if not routes:
        logger.info(f"No routes configured for event: {full_event}")
        return {"status": "ignored", "event": full_event}

    # Process each applicable route
    results = []
    for route in routes:
        try:
            # Build message using route's message builder
            message = route.message_builder(payload)

            # Enrich message with additional data if needed (e.g., modified files for PRs)
            if route.workflow_name == "review" and "pull_request" in payload:
                pr_url = payload["pull_request"]["url"]
                message["modified_files"] = await get_pr_modified_files(pr_url)

            # Publish to the workflow's queue
            publish_to_queue(message, route.queue_name, channel)

            results.append(
                {
                    "workflow": route.workflow_name,
                    "queue": route.queue_name,
                    "status": "queued",
                }
            )

            logger.info(
                f"Queued {route.workflow_name} for PR {payload.get('pull_request', {}).get('number', 'N/A')}"
            )

        except Exception as e:
            logger.error(f"Failed to route to {route.workflow_name}: {e}")
            results.append(
                {
                    "workflow": route.workflow_name,
                    "status": "failed",
                    "error": str(e),
                }
            )

    return {"status": "processed", "event": full_event, "routes": results}

if __name__ == "__main__":
    uvicorn.run("main:app", port=9000, reload=True)