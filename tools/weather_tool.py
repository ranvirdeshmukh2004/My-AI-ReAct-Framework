"""
weather_tool.py — Weather Information Tool
=============================================
Gets current weather for any city using the free
wttr.in service. No API key required!

Supports:
- Current temperature, humidity, wind
- Weather description
- Any city worldwide
"""

import httpx
from tools.base import Tool


def get_weather(location: str) -> str:
    """
    Get current weather for a location.
    
    Args:
        location: City name or location string.
                  Examples: "London", "New York", "Tokyo"
    
    Returns:
        Formatted weather information string.
    """
    location = location.strip().strip("'\"")

    try:
        # wttr.in provides free weather data in JSON format
        url = f"https://wttr.in/{location}?format=j1"

        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers={"User-Agent": "AI-Agent/1.0"})

        if response.status_code != 200:
            return f"Could not fetch weather for '{location}'. Please check the city name."

        data = response.json()

        # Extract current conditions
        current = data["current_condition"][0]
        area = data["nearest_area"][0]

        city = area["areaName"][0]["value"]
        country = area["country"][0]["value"]
        temp_c = current["temp_C"]
        temp_f = current["temp_F"]
        feels_like_c = current["FeelsLikeC"]
        humidity = current["humidity"]
        description = current["weatherDesc"][0]["value"]
        wind_speed = current["windspeedKmph"]
        wind_dir = current["winddir16Point"]
        visibility = current["visibility"]
        uv_index = current["uvIndex"]

        result = (
            f"🌍 Weather for {city}, {country}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌡️  Temperature: {temp_c}°C ({temp_f}°F)\n"
            f"🤔 Feels Like: {feels_like_c}°C\n"
            f"☁️  Condition: {description}\n"
            f"💧 Humidity: {humidity}%\n"
            f"💨 Wind: {wind_speed} km/h {wind_dir}\n"
            f"👁️  Visibility: {visibility} km\n"
            f"☀️  UV Index: {uv_index}"
        )

        return result

    except Exception as e:
        return f"Weather error: {str(e)}. Please try a different city name."


# ============================================
# Register as a Tool
# ============================================

weather_tool = Tool(
    name="weather",
    description=(
        "Get current weather information for any city worldwide. "
        "Returns temperature, humidity, wind, and conditions. "
        "Input should be a city name like 'London' or 'New York'."
    ),
    function=get_weather,
)
