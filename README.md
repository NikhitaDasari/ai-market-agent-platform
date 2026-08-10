# 🌦️ Weather Prediction MCP Server + Agent Bricks

This project implements a weather-focused MCP server that integrates with Databricks Agent Bricks.

The solution uses:

- FastMCP for the MCP server
- Open-Meteo for live weather data
- Databricks Apps for deployment
- Databricks Agent Bricks for the AI agent
- Lakebase for MCP activity logging
- Flask for the monitoring dashboard

The goal of this project is to demonstrate an AI agent that can call tools to retrieve live weather data, generate practical recommendations, and log tool activity for observability.

---

## Project Overview

The Weather Agent supports three main capabilities:

1. Current weather lookup
2. Multi-day weather forecasts
3. Weather-based recommendations for activities, clothing, and umbrella use

The Agent Bricks agent does not generate current weather information from its own knowledge. It calls the Weather MCP tools and uses the returned data to answer the user.

---

## Architecture

```text
User
  |
  v
Databricks Agent Bricks
  |
  | MCP
  v
Weather MCP Server
  |
  +--------------------------+
  |                          |
  v                          v
Open-Meteo API            Lakebase
Live weather data         MCP activity log
                             |
                             v
                      Weather Dashboard


                      Weather API

This project uses the Open-Meteo API for weather data.

Open-Meteo provides:

Location geocoding
Current weather conditions
Daily forecasts
Temperature
Humidity
Precipitation
Wind speed
Weather condition codes

No API key is required.

Weather Broker

weather_broker.py contains all external weather API communication and response parsing.

The MCP tool layer does not make raw HTTP requests directly.

Main Broker Functions
resolve_location(location)


Recommendation Logic

The recommendation tool currently applies the following application-defined rules:

Recommend an umbrella when precipitation probability is at least 40%
Recommend a light jacket when the forecast low is below 60°F
Recommend a warm coat when the forecast low is below 45°F
Flag heat caution when the forecast high is at least 95°F
Flag wind caution when maximum wind speed is at least 25 mph
Mark outdoor plans as Use caution when rain, wind, or extreme heat exceeds configured thresholds

The tool also returns the reasons behind each recommendation.


MCP Activity Logging

Every MCP tool invocation is logged to Lakebase.

The activity table is:

weather_mcp_activity

Schema:

CREATE TABLE weather_mcp_activity (
    id TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    location TEXT,
    request_params JSONB,
    result JSONB,
    status TEXT NOT NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

An index is also created for recent activity queries:

CREATE INDEX idx_weather_mcp_activity_created_at
ON weather_mcp_activity (created_at DESC);

The MCP server logs:

Tool name
Location
Request parameters
Tool result
Success or error status
Error message
Timestamp

This provides a simple audit and observability layer for Agent Bricks activity.


Lakebase Connection

Lakebase connectivity is stored using Databricks Secrets.

The applications expect:

Secret scope: database
Secret key: lakebase-url

The value of lakebase-url is the PostgreSQL connection string for the Lakebase database.

Example format:

postgresql://<user>:<password>@<host>/<database>?sslmode=require

The MCP server and dashboard both use the same Lakebase connection.

The Open-Meteo API itself does not require credentials.

MCP Server

The MCP server is implemented using FastMCP.

The server exposes the three weather functions using @mcp.tool.



Agent Bricks Configuration

The deployed Weather MCP server is registered with Databricks as an external MCP server.

The Agent Bricks agent is configured to use the Weather MCP tools rather than answering current weather questions from model knowledge.

Agent Instructions:
You are a weather assistant that answers questions using the connected Weather Prediction MCP tools.

Always use the Weather MCP tools for current conditions, forecasts, and weather recommendations. Never invent or guess weather data.

Tool usage:
- Use get_current_weather when the user asks about current or right-now weather.
- Use get_forecast when the user asks about upcoming weather, tomorrow, this weekend, or the next several days.
- Use get_weather_recommendation when the user asks whether they need an umbrella, jacket, whether outdoor plans are advisable, or another recommendation based on weather conditions.

Rules:
1. Do not answer weather questions from your own knowledge. Call the appropriate MCP tool first.
2. Only provide weather values that were returned successfully by a tool.
3. If a tool returns status="error", explain that the weather information could not be retrieved. Do not fabricate an answer.
4. If a location is missing or ambiguous, ask the user to provide or clarify the location.
5. When dates such as "tomorrow" or "this weekend" are used, resolve them to the appropriate calendar date before calling a recommendation tool that requires YYYY-MM-DD.
6. Summarize tool results naturally instead of dumping raw JSON.
7. When making recommendations, explain the relevant forecast values behind the recommendation.
8. Keep responses concise and practical.




Weather Dashboard

A separate Flask-based Databricks App provides visibility into recent Agent Bricks activity.

The dashboard does not call the MCP tools itself.

Instead, it reads activity that the Weather MCP server has already written to Lakebase.

The dashboard displays:

Total MCP tool calls
Successful calls
Failed calls
Number of locations queried
Tool usage counts
Recent Agent Bricks activity
Weather results
Recommendations
Errors

The dashboard includes:

Manual Refresh button
Automatic refresh every 10 seconds



Separation of Responsibilities

The project intentionally separates responsibilities across components.

weather_broker.py

Responsible for:

Open-Meteo HTTP requests
Location resolution
Weather response parsing
Recommendation logic
weather_mcp_server.py

Responsible for:

MCP tool definitions
Tool-level error handling
Lakebase activity logging
MCP HTTP server
lakebase.py

Responsible for:

Lakebase connection management
SQL reads
SQL writes
dashboard/app.py

Responsible for:

Flask routes
Reading activity from Lakebase
Serving dashboard data
dashboard/templates/index.html

Responsible for:

Human-facing UI
Summary cards
Tool usage table
Recent activity table
Automatic refresh


Future Enhancements

Possible future enhancements include:

Severe weather alerts
Hourly weather forecasts
Historical weather lookup
Multi-city comparison
Travel recommendations
Outdoor activity scoring
User favorite locations
Personalized weather preferences
Weather history analytics
Dashboard filtering
Usage charts
Agent feedback tracking
Summary

The Weather Prediction MCP project demonstrates an end-to-end AI agent architecture using Databricks.

A Databricks Agent Bricks agent connects to a custom FastMCP server and uses live Open-Meteo weather data to answer current-weather questions, provide multi-day forecasts, and generate practical recommendations.

The MCP server stores tool activity in Lakebase, while a separate Flask-based Databricks App provides a dashboard for monitoring agent behavior and tool usage.