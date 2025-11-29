"""
Agent caller abstraction. Currently supports real HTTP calls only; if an agent
is not reachable or misconfigured we return a structured error instead of
simulating output. This keeps execution transparent for observability and
alignment with production behavior.
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Dict

try:
    import httpx  # type: ignore
except ImportError:
    httpx = None

from .models import AgentMetadata, AgentRequest, AgentResponse, ErrorModel, OutputModel


async def call_agent(
    agent_meta: AgentMetadata,
    intent: str,
    text: str,
    context: Dict[str, Any],
    custom_input: Dict[str, Any] = None,
) -> AgentResponse:
    """
    Build handshake request and invoke the worker. When endpoints are not real,
    we fall back to simulated results that mirror the contract.
    
    Args:
        custom_input: Optional dict to override default input structure.
                     If provided, it replaces the entire input payload.
    """

    request_id = str(uuid.uuid4())
    
    # Use custom_input if provided, otherwise use default structure
    input_payload = custom_input if custom_input is not None else {
        "text": text, 
        "metadata": {"language": "en", "extra": {}}
    }
    
    handshake = AgentRequest(
        request_id=request_id,
        agent_name=agent_meta.name,
        intent=intent,
        input=input_payload,
        context=context,
    )

    # Only live HTTP calls are supported; no simulation fallback.
    if agent_meta.type == "http" and agent_meta.endpoint and httpx is not None:
        try:
            async with httpx.AsyncClient(timeout=agent_meta.timeout_ms / 1000) as client:
                resp = await client.post(agent_meta.endpoint, json=handshake.dict())
                if resp.status_code != 200:
                    return AgentResponse(
                        request_id=request_id,
                        agent_name=agent_meta.name,
                        status="error",
                        error=ErrorModel(
                            type="http_error",
                            message=f"HTTP {resp.status_code} calling {agent_meta.endpoint}",
                        ),
                    )
                return AgentResponse(**resp.json())
        except Exception as exc:
            return AgentResponse(
                request_id=request_id,
                agent_name=agent_meta.name,
                status="error",
                error=ErrorModel(type="network_error", message=str(exc)),
            )
    elif agent_meta.type == "http" and httpx is None:
        return AgentResponse(
            request_id=request_id,
            agent_name=agent_meta.name,
            status="error",
            error=ErrorModel(type="config_error", message="httpx not installed for HTTP agent calls"),
        )
    elif agent_meta.type == "cli":
        return AgentResponse(
            request_id=request_id,
            agent_name=agent_meta.name,
            status="error",
            error=ErrorModel(type="not_implemented", message="CLI agent execution is not implemented"),
        )
    else:
        return AgentResponse(
            request_id=request_id,
            agent_name=agent_meta.name,
            status="error",
            error=ErrorModel(type="config_error", message="Agent endpoint/command not configured"),
        )
