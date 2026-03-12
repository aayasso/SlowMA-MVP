"""
SlowMA Cost Logger
Wraps every Anthropic API call to log token usage and estimated cost.

Usage:
    from app.cost_logger import tracked_completion

    response = tracked_completion(
        client=anthropic_client,
        feature="activity_generation",
        user_id=user_id,
        journey_id=journey_id,
        housen_stage=current_stage,
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    # response is a normal Anthropic message object
"""

import time
from typing import Optional

from app.database import get_supabase

# ============================================================
# Pricing (USD per million tokens, as of March 2026)
# Update these if Anthropic changes pricing
# ============================================================
PRICING = {
    "claude-sonnet-4-20250514": {
        "input_per_million": 3.00,
        "output_per_million": 15.00,
    },
    "claude-opus-4-20250514": {
        "input_per_million": 15.00,
        "output_per_million": 75.00,
    },
    "claude-haiku-4-20250514": {
        "input_per_million": 0.80,
        "output_per_million": 4.00,
    },
}

DEFAULT_PRICING = {
    "input_per_million": 3.00,
    "output_per_million": 15.00,
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate estimated USD cost from token counts."""
    pricing = PRICING.get(model, DEFAULT_PRICING)
    input_cost = (input_tokens / 1_000_000) * pricing["input_per_million"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_per_million"]
    return round(input_cost + output_cost, 6)


def log_usage(
    feature: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    success: bool,
    user_id: Optional[str] = None,
    journey_id: Optional[str] = None,
    classroom_id: Optional[str] = None,
    assignment_id: Optional[str] = None,
    housen_stage: Optional[int] = None,
    error_message: Optional[str] = None,
):
    """Write a usage record to api_usage_logs. Never raises — logging must not break the app."""
    try:
        total_tokens = input_tokens + output_tokens
        estimated_cost = estimate_cost(model, input_tokens, output_tokens)

        record = {
            "feature": feature,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost,
            "latency_ms": latency_ms,
            "success": success,
            "user_id": user_id,
            "journey_id": journey_id,
            "classroom_id": classroom_id,
            "assignment_id": assignment_id,
            "housen_stage": housen_stage,
            "error_message": error_message,
        }

        db = get_supabase()
        db.table("api_usage_logs").insert(record).execute()

    except Exception as e:
        # Never let logging failure affect the main application flow
        print(f"Warning: cost logging failed: {e}")


def tracked_completion(
    client,
    feature: str,
    model: str,
    max_tokens: int,
    messages: list,
    user_id: Optional[str] = None,
    journey_id: Optional[str] = None,
    classroom_id: Optional[str] = None,
    assignment_id: Optional[str] = None,
    housen_stage: Optional[int] = None,
    system: Optional[str] = None,
):
    """
    Drop-in replacement for client.messages.create() that automatically
    logs token usage and cost to api_usage_logs.

    Returns the normal Anthropic message object unchanged.
    """
    start_time = time.time()
    success = True
    error_message = None
    response = None

    try:
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        response = client.messages.create(**kwargs)
        return response

    except Exception as e:
        success = False
        error_message = str(e)
        raise

    finally:
        latency_ms = int((time.time() - start_time) * 1000)

        input_tokens = 0
        output_tokens = 0
        if response and hasattr(response, "usage"):
            input_tokens = response.usage.input_tokens or 0
            output_tokens = response.usage.output_tokens or 0

        log_usage(
            feature=feature,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            success=success,
            user_id=user_id,
            journey_id=journey_id,
            classroom_id=classroom_id,
            assignment_id=assignment_id,
            housen_stage=housen_stage,
            error_message=error_message,
        )