"""
Weather Agent dashboard.

This is a small Flask app used to WATCH what the Agent Bricks agent is
doing through the Weather MCP server.

The dashboard does not invoke MCP tools itself. It reads the MCP activity
log stored in Lakebase and displays recent weather tool calls,
recommendations, and errors.

Deploy this as its OWN Databricks App, separate from weather_mcp_server.py.

Run locally:
    python dashboard_app.py
"""

import os

from flask import Flask, jsonify, render_template, request

import lakebase


app = Flask(__name__)


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.errorhandler(Exception)
def handle_exception(err):
    """Ensure unhandled errors return JSON instead of an HTML error page."""

    status_code = getattr(err, "code", 500)

    if not isinstance(status_code, int):
        status_code = 500

    return jsonify({
        "error": str(err)
    }), status_code


@app.route("/")
def index():
    """Human-facing dashboard."""
    return render_template("index.html")


@app.route("/api/activity")
def api_activity():
    """
    Return recent Weather MCP tool calls, newest first.

    Query params:
        limit: maximum number of activity records to return.
    """

    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        return jsonify({
            "error": "limit must be an integer"
        }), 400

    limit = max(1, min(limit, 200))

    rows = lakebase.run_query(
        """
        SELECT
            id,
            tool_name,
            location,
            request_params,
            result,
            status,
            error_message,
            created_at
        FROM weather_mcp_activity
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (limit,),
    )

    return jsonify(rows)


@app.route("/api/stats")
def api_stats():
    """Return basic MCP usage statistics."""

    rows = lakebase.run_query(
        """
        SELECT
            COUNT(*) AS total_calls,
            COUNT(*) FILTER (
                WHERE status = 'success'
            ) AS successful_calls,
            COUNT(*) FILTER (
                WHERE status = 'error'
            ) AS failed_calls,
            COUNT(DISTINCT location) AS locations_queried
        FROM weather_mcp_activity
        """
    )

    return jsonify(rows[0] if rows else {
        "total_calls": 0,
        "successful_calls": 0,
        "failed_calls": 0,
        "locations_queried": 0,
    })


@app.route("/api/tools")
def api_tools():
    """Return tool usage grouped by MCP tool name."""

    rows = lakebase.run_query(
        """
        SELECT
            tool_name,
            COUNT(*) AS call_count
        FROM weather_mcp_activity
        GROUP BY tool_name
        ORDER BY call_count DESC
        """
    )

    return jsonify(rows)


if __name__ == "__main__":

    host = os.getenv(
        "FLASK_RUN_HOST",
        "0.0.0.0",
    )

    port = int(
        os.getenv(
            "DATABRICKS_APP_PORT",
            os.getenv("FLASK_RUN_PORT", 8001),
        )
    )

    app.run(
        debug=True,
        host=host,
        port=port,
    )