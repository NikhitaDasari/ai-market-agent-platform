"""
Weather data adapter backing the Weather MCP server.

This module is a thin wrapper around the Open-Meteo APIs.

Responsibilities:
- Resolve human-readable locations into latitude/longitude
- Fetch current weather conditions
- Fetch multi-day forecasts
- Generate a simple weather recommendation from forecast data
- Return clean Python dictionaries for the MCP tool layer

The MCP server should not contain raw HTTP/API parsing logic.
All external API communication lives in this module.

Open-Meteo does not require an API key.
"""

from datetime import date, datetime

import requests


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

_GEOCODING_BASE_URL = "https://geocoding-api.open-meteo.com/v1"
_FORECAST_BASE_URL = "https://api.open-meteo.com/v1"

_DEFAULT_TIMEOUT = 30

_session = requests.Session()


# -------------------------------------------------------------------
# Weather-code descriptions
# -------------------------------------------------------------------

# Open-Meteo uses WMO weather interpretation codes.
_WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def _weather_description(code: int | None) -> str:
    """Convert an Open-Meteo weather code to readable text."""

    if code is None:
        return "Unknown"

    return _WEATHER_CODES.get(int(code), f"Weather code {code}")


# -------------------------------------------------------------------
# Location resolution
# -------------------------------------------------------------------

def resolve_location(location: str) -> dict:
    """
    Resolve a human-readable location into coordinates.

    Args:
        location: City or place name, such as "Dallas, TX".

    Returns:
        Dictionary containing:
        - name
        - latitude
        - longitude
        - country
        - region
        - timezone

    Raises:
        ValueError: If the location is empty or cannot be resolved.
        requests.HTTPError: If the Open-Meteo API request fails.
    """

    if not isinstance(location, str):
        raise ValueError("location must be a string")

    location = location.strip()

    if not location:
        raise ValueError("location must not be empty")

    response = _session.get(
        f"{_GEOCODING_BASE_URL}/search",
        params={
            "name": location,
            "count": 1,
            "language": "en",
            "format": "json",
        },
        timeout=_DEFAULT_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()
    results = data.get("results") or []

    if not results:
        raise ValueError(
            f"Could not resolve weather location: {location!r}"
        )

    match = results[0]

    return {
        "name": match.get("name"),
        "latitude": match.get("latitude"),
        "longitude": match.get("longitude"),
        "country": match.get("country"),
        "region": match.get("admin1"),
        "timezone": match.get("timezone"),
    }


# -------------------------------------------------------------------
# Current weather
# -------------------------------------------------------------------

def get_current_weather(location: str) -> dict:
    """
    Get current weather conditions for a location.

    Args:
        location: Human-readable place name such as "Dallas, TX".

    Returns:
        Dictionary containing the resolved location plus:
        - temperature
        - apparent_temperature
        - humidity
        - wind_speed
        - precipitation
        - weather_code
        - conditions
        - observed_at

    Raises:
        ValueError: If the location cannot be resolved.
        RuntimeError: If current weather data is missing.
        requests.HTTPError: If the API request fails.
    """

    resolved = resolve_location(location)

    response = _session.get(
        f"{_FORECAST_BASE_URL}/forecast",
        params={
            "latitude": resolved["latitude"],
            "longitude": resolved["longitude"],
            "current": ",".join(
                [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "precipitation",
                    "weather_code",
                    "wind_speed_10m",
                ]
            ),
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": resolved["timezone"] or "auto",
        },
        timeout=_DEFAULT_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()
    current = data.get("current")

    if not current:
        raise RuntimeError(
            f"No current weather data returned for {location!r}"
        )

    weather_code = current.get("weather_code")

    return {
        "location": resolved["name"],
        "region": resolved["region"],
        "country": resolved["country"],
        "latitude": resolved["latitude"],
        "longitude": resolved["longitude"],
        "timezone": resolved["timezone"],
        "temperature_f": current.get("temperature_2m"),
        "apparent_temperature_f": current.get(
            "apparent_temperature"
        ),
        "humidity_percent": current.get(
            "relative_humidity_2m"
        ),
        "wind_speed_mph": current.get("wind_speed_10m"),
        "precipitation_in": current.get("precipitation"),
        "weather_code": weather_code,
        "conditions": _weather_description(weather_code),
        "observed_at": current.get("time"),
    }


# -------------------------------------------------------------------
# Forecast
# -------------------------------------------------------------------

def get_forecast(location: str, days: int = 3) -> dict:
    """
    Get a multi-day weather forecast.

    Args:
        location: Human-readable place name such as "Chicago, IL".
        days: Number of forecast days to return. Must be between 1 and 7.

    Returns:
        Dictionary containing the resolved location and a list of daily
        forecasts. Each forecast includes:
        - date
        - high temperature
        - low temperature
        - precipitation probability
        - weather conditions
        - maximum wind speed

    Raises:
        ValueError: If days is outside 1-7 or location cannot be resolved.
        RuntimeError: If forecast data is missing.
        requests.HTTPError: If the API request fails.
    """

    try:
        days = int(days)
    except (TypeError, ValueError):
        raise ValueError("days must be an integer")

    if days < 1 or days > 7:
        raise ValueError("days must be between 1 and 7")

    resolved = resolve_location(location)

    response = _session.get(
        f"{_FORECAST_BASE_URL}/forecast",
        params={
            "latitude": resolved["latitude"],
            "longitude": resolved["longitude"],
            "daily": ",".join(
                [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_probability_max",
                    "precipitation_sum",
                    "wind_speed_10m_max",
                ]
            ),
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": resolved["timezone"] or "auto",
            "forecast_days": days,
        },
        timeout=_DEFAULT_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()
    daily = data.get("daily")

    if not daily:
        raise RuntimeError(
            f"No forecast data returned for {location!r}"
        )

    forecast_dates = daily.get("time", [])

    forecasts = []

    for index, forecast_date in enumerate(forecast_dates):

        weather_code = _safe_list_value(
            daily.get("weather_code"),
            index,
        )

        forecasts.append(
            {
                "date": forecast_date,
                "temperature_high_f": _safe_list_value(
                    daily.get("temperature_2m_max"),
                    index,
                ),
                "temperature_low_f": _safe_list_value(
                    daily.get("temperature_2m_min"),
                    index,
                ),
                "precipitation_probability_percent":
                    _safe_list_value(
                        daily.get(
                            "precipitation_probability_max"
                        ),
                        index,
                    ),
                "precipitation_in": _safe_list_value(
                    daily.get("precipitation_sum"),
                    index,
                ),
                "max_wind_speed_mph": _safe_list_value(
                    daily.get("wind_speed_10m_max"),
                    index,
                ),
                "weather_code": weather_code,
                "conditions": _weather_description(
                    weather_code
                ),
            }
        )

    return {
        "location": resolved["name"],
        "region": resolved["region"],
        "country": resolved["country"],
        "latitude": resolved["latitude"],
        "longitude": resolved["longitude"],
        "timezone": resolved["timezone"],
        "days": forecasts,
    }


# -------------------------------------------------------------------
# Weather recommendation / prediction
# -------------------------------------------------------------------

def get_weather_recommendation(
    location: str,
    forecast_date: str,
) -> dict:
    """
    Generate simple recommendations for a location and date.

    This function derives recommendations from forecast data rather than
    simply returning raw API values.

    Rules:
    - Umbrella recommended when precipitation probability >= 40%
    - Rain caution when expected precipitation > 0.10 inches
    - Jacket recommended when forecast low < 60 F
    - Warm coat recommended when forecast low < 45 F
    - Heat caution when forecast high >= 95 F
    - Wind caution when maximum wind speed >= 25 mph
    - Outdoor plans are marked "use caution" when precipitation probability
      is >= 60%, wind is >= 25 mph, or high temperature is >= 100 F

    Args:
        location:
            Human-readable place name such as "Austin, TX".

        forecast_date:
            Date in YYYY-MM-DD format.

    Returns:
        Dictionary containing the forecast and derived recommendations.

    Raises:
        ValueError:
            If the date format is invalid, the requested date is not
            available in the forecast, or the location cannot be resolved.
    """

    # Validate date format.
    try:
        datetime.strptime(
            forecast_date,
            "%Y-%m-%d",
        )
    except (TypeError, ValueError):
        raise ValueError(
            "forecast_date must use YYYY-MM-DD format"
        )

    # Fetch the full supported forecast window.
    #
    # Do not calculate the number of days using date.today(), because
    # Databricks may run in UTC while the requested location is in another
    # timezone. Around midnight UTC this can cause an off-by-one-day error.
    forecast = get_forecast(
        location,
        days=7,
    )

    matching_day = None

    for day in forecast["days"]:
        if day["date"] == forecast_date:
            matching_day = day
            break

    if matching_day is None:
        available_dates = [
            day["date"]
            for day in forecast["days"]
        ]

        raise ValueError(
            f"No forecast available for {forecast_date} "
            f"in {location!r}. "
            f"Available dates: {available_dates}"
        )

    precipitation_probability = (
        matching_day.get(
            "precipitation_probability_percent"
        )
        or 0
    )

    precipitation_amount = (
        matching_day.get("precipitation_in")
        or 0
    )

    temperature_low = matching_day.get(
        "temperature_low_f"
    )

    temperature_high = matching_day.get(
        "temperature_high_f"
    )

    wind_speed = (
        matching_day.get("max_wind_speed_mph")
        or 0
    )

    # ---------------------------------------------------------------
    # Derived recommendation logic
    # ---------------------------------------------------------------

    umbrella_needed = (
        precipitation_probability >= 40
    )

    if temperature_low is None:
        clothing = (
            "No clothing recommendation available"
        )

    elif temperature_low < 45:
        clothing = "Warm coat recommended"

    elif temperature_low < 60:
        clothing = "Light jacket recommended"

    else:
        clothing = "No jacket likely needed"

    heat_caution = (
        temperature_high is not None
        and temperature_high >= 95
    )

    wind_caution = wind_speed >= 25

    rain_caution = (
        precipitation_probability >= 60
        or precipitation_amount > 0.10
    )

    outdoor_caution = (
        rain_caution
        or wind_caution
        or (
            temperature_high is not None
            and temperature_high >= 100
        )
    )

    reasons = []

    if umbrella_needed:
        reasons.append(
            f"precipitation probability is "
            f"{precipitation_probability}%"
        )

    if precipitation_amount > 0.10:
        reasons.append(
            f"forecast precipitation is "
            f"{precipitation_amount} inches"
        )

    if (
        temperature_low is not None
        and temperature_low < 60
    ):
        reasons.append(
            f"forecast low is {temperature_low} F"
        )

    if heat_caution:
        reasons.append(
            f"forecast high is {temperature_high} F"
        )

    if wind_caution:
        reasons.append(
            f"maximum wind speed is {wind_speed} mph"
        )

    if not reasons:
        reasons.append(
            "forecast conditions do not cross any "
            "configured caution thresholds"
        )

    return {
        "location": forecast["location"],
        "region": forecast["region"],
        "country": forecast["country"],
        "date": forecast_date,
        "forecast": matching_day,
        "recommendations": {
            "bring_umbrella": umbrella_needed,
            "clothing": clothing,
            "heat_caution": heat_caution,
            "wind_caution": wind_caution,
            "outdoor_plans": (
                "Use caution"
                if outdoor_caution
                else "Generally favorable"
            ),
        },
        "reasoning": reasons,
    }

    
# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _safe_list_value(
    values: list | None,
    index: int,
):
    """
    Safely retrieve an item from an Open-Meteo array response.
    """

    if not values:
        return None

    if index >= len(values):
        return None

    return values[index]