"""
Weather Prediction MCP Server.

Exposes weather tools over MCP (Model Context Protocol) so a Databricks
Agent Bricks agent can retrieve live weather information and make simple
weather-based recommendations.

Tools:
- get_current_weather(location)
- get_forecast(location, days)
- get_weather_recommendation(location, forecast_date)

Weather API calls and parsing are handled by weather_broker.py.

Each MCP tool call is also logged to Lakebase so a separate dashboard
Databricks App can display recent agent/tool activity.

Run locally:
    python weather_mcp_server.py
"""

import json
import logging
import os
import uuid

from fastmcp import FastMCP

import lakebase
import weather_broker


# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("weather-mcp-server")


# -------------------------------------------------------------------
# MCP server
# -------------------------------------------------------------------

mcp = FastMCP("weather-prediction")


# -------------------------------------------------------------------
# Lakebase activity logging
# -------------------------------------------------------------------

ACTIVITY_TABLE_NAME = os.environ.get(
    "WEATHER_ACTIVITY_TABLE_NAME",
    "weather_mcp_activity",
)


def ensure_activity_table():
    """
    Create the Weather MCP activity table if it does not already exist.

    The dashboard reads this table to show recent Agent Bricks / MCP
    interactions.
    """

    lakebase.run_write(
        f"""
        CREATE TABLE IF NOT EXISTS {ACTIVITY_TABLE_NAME} (
            id TEXT PRIMARY KEY,
            tool_name TEXT NOT NULL,
            location TEXT,
            request_params JSONB,
            result JSONB,
            status TEXT NOT NULL,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    lakebase.run_write(
        f"""
        CREATE INDEX IF NOT EXISTS
            idx_{ACTIVITY_TABLE_NAME}_created_at
        ON {ACTIVITY_TABLE_NAME} (created_at DESC)
        """
    )


def log_activity(
    tool_name: str,
    location: str | None,
    request_params: dict,
    result: dict | None,
    status: str,
    error_message: str | None = None,
):
    """
    Persist one MCP tool invocation to Lakebase.

    Logging failures should not prevent the actual weather tool from
    returning its result to the agent.
    """

    try:
        ensure_activity_table()

        lakebase.run_write(
            f"""
            INSERT INTO {ACTIVITY_TABLE_NAME} (
                id,
                tool_name,
                location,
                request_params,
                result,
                status,
                error_message,
                created_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                now()
            )
            """,
            (
                str(uuid.uuid4()),
                tool_name,
                location,
                json.dumps(request_params),
                json.dumps(result)
                if result is not None
                else None,
                status,
                error_message,
            ),
        )

    except Exception:
        # The weather tool should still succeed even if observability
        # logging temporarily fails.
        logger.exception(
            "Failed to log MCP activity for tool %s",
            tool_name,
        )


# -------------------------------------------------------------------
# MCP Tool 1: Current weather
# -------------------------------------------------------------------

@mcp.tool
def get_current_weather(location: str) -> dict:
    """
    Get the current weather conditions for a location.

    Use this tool when the user asks about weather right now or current
    conditions.

    Args:
        location:
            Human-readable city or place name, for example:
            "Dallas, TX"
            "Chicago, IL"
            "Austin, TX"

    Returns:
        A dictionary containing:
        - temperature in Fahrenheit
        - apparent temperature in Fahrenheit
        - humidity percentage
        - precipitation
        - wind speed in mph
        - readable weather conditions
        - observation time

        If the location cannot be resolved or the weather API fails,
        returns a clean error dictionary.
    """

    params = {
        "location": location,
    }

    try:
        data = weather_broker.get_current_weather(
            location
        )

        log_activity(
            tool_name="get_current_weather",
            location=location,
            request_params=params,
            result=data,
            status="success",
        )

        return {
            "status": "success",
            "data": data,
        }

    except Exception as exc:
        logger.exception(
            "Failed to get current weather for %s",
            location,
        )

        log_activity(
            tool_name="get_current_weather",
            location=location,
            request_params=params,
            result=None,
            status="error",
            error_message=str(exc),
        )

        return {
            "status": "error",
            "message": (
                f"Unable to retrieve current weather "
                f"for {location!r}: {str(exc)}"
            ),
        }


# -------------------------------------------------------------------
# MCP Tool 2: Forecast
# -------------------------------------------------------------------

@mcp.tool
def get_forecast(
    location: str,
    days: int = 3,
) -> dict:
    """
    Get a multi-day weather forecast for a location.

    Use this tool when the user asks about upcoming weather, tomorrow,
    this weekend, or the next several days.

    Args:
        location:
            Human-readable city or place name such as
            "Dallas, TX" or "Chicago, IL".

        days:
            Number of forecast days to retrieve.
            Must be between 1 and 7.

    Returns:
        A dictionary containing the resolved location and daily forecasts.

        Each forecast day includes:
        - date
        - high temperature
        - low temperature
        - precipitation probability
        - expected precipitation
        - maximum wind speed
        - readable weather conditions

        If the request fails, returns a clean error dictionary.
    """

    params = {
        "location": location,
        "days": days,
    }

    try:
        data = weather_broker.get_forecast(
            location,
            days,
        )

        log_activity(
            tool_name="get_forecast",
            location=location,
            request_params=params,
            result=data,
            status="success",
        )

        return {
            "status": "success",
            "data": data,
        }

    except Exception as exc:
        logger.exception(
            "Failed to get forecast for %s",
            location,
        )

        log_activity(
            tool_name="get_forecast",
            location=location,
            request_params=params,
            result=None,
            status="error",
            error_message=str(exc),
        )

        return {
            "status": "error",
            "message": (
                f"Unable to retrieve forecast "
                f"for {location!r}: {str(exc)}"
            ),
        }


# -------------------------------------------------------------------
# MCP Tool 3: Weather recommendation
# -------------------------------------------------------------------

@mcp.tool
def get_weather_recommendation(
    location: str,
    forecast_date: str,
) -> dict:
    """
    Generate practical weather recommendations for a location and date.

    Use this tool when the user asks a judgment-based weather question,
    for example:

    - "Should I bring an umbrella tomorrow?"
    - "Do I need a jacket in Austin this weekend?"
    - "Is Saturday good for outdoor plans?"
    - "Will it be too hot to spend time outside?"

    This tool does more than return raw forecast data. It applies explicit
    recommendation rules to the forecast.

    Current rules:
    - Recommend an umbrella when precipitation probability is >= 40%.
    - Recommend a light jacket when the forecast low is below 60 F.
    - Recommend a warm coat when the forecast low is below 45 F.
    - Flag heat caution when the forecast high is >= 95 F.
    - Flag wind caution when maximum wind speed is >= 25 mph.
    - Mark outdoor plans "Use caution" when rain, heat, or wind crosses
      configured thresholds.

    Args:
        location:
            Human-readable city or place name such as
            "Dallas, TX" or "Austin, TX".

        forecast_date:
            Requested forecast date in YYYY-MM-DD format.

    Returns:
        A dictionary containing:
        - matching daily forecast
        - umbrella recommendation
        - clothing recommendation
        - heat caution
        - wind caution
        - outdoor-plan recommendation
        - reasons explaining the recommendation

        If the location/date cannot be handled or the weather API fails,
        returns a clean error dictionary.
    """

    params = {
        "location": location,
        "forecast_date": forecast_date,
    }

    try:
        data = (
            weather_broker.get_weather_recommendation(
                location,
                forecast_date,
            )
        )

        log_activity(
            tool_name="get_weather_recommendation",
            location=location,
            request_params=params,
            result=data,
            status="success",
        )

        return {
            "status": "success",
            "data": data,
        }

    except Exception as exc:
        logger.exception(
            "Failed to generate weather recommendation "
            "for %s on %s",
            location,
            forecast_date,
        )

        log_activity(
            tool_name="get_weather_recommendation",
            location=location,
            request_params=params,
            result=None,
            status="error",
            error_message=str(exc),
        )

        return {
            "status": "error",
            "message": (
                f"Unable to generate a weather recommendation "
                f"for {location!r} on {forecast_date}: "
                f"{str(exc)}"
            ),
        }


# -------------------------------------------------------------------
# Run MCP server
# -------------------------------------------------------------------

if __name__ == "__main__":

    # Create the logging table during startup when possible.
    #
    # If Lakebase is temporarily unavailable, log the failure but still
    # allow the MCP server to start. Each tool call will retry logging.
    try:
        ensure_activity_table()
        logger.info(
            "Weather MCP activity table is ready"
        )

    except Exception:
        logger.exception(
            "Could not initialize Weather MCP "
            "activity table during startup"
        )

    # Databricks Apps route external traffic to DATABRICKS_APP_PORT.
    # PORT is retained as a fallback for other environments.
    port = int(
        os.getenv(
            "DATABRICKS_APP_PORT",
            os.getenv("PORT", 8000),
        )
    )

    logger.info(
        "Starting Weather MCP server on port %s",
        port,
    )

    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=port,
    )