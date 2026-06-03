"""
Functions for retrieving weather information.
"""

import requests


_weather_codes = {
    0: "☀️ Clear Sky",
    1: "🌤️ Mostly Clear",
    2: "⛅ Partly Cloudy",
    3: "☁️ Overcast",
    45: "🌫️ Fog",
    48: "🌫️ Freezing Fog",
    51: "🌦️ Light Drizzle",
    53: "🌦️ Drizzle",
    55: "🌧️ Heavy Drizzle",
    61: "🌦️ Light Rain",
    63: "🌧️ Rain",
    65: "🌧️ Heavy Rain",
    71: "❄️ Light Snow",
    73: "❄️ Snow",
    75: "❄️ Heavy Snow",
    80: "🌦️ Rain Showers",
    81: "🌧️ Heavy Showers",
    95: "⛈️ Thunderstorm",
    96: "⛈️ Thunderstorm + Hail",
    99: "⛈️ Severe Thunderstorm + Hail",
}


def _parse_condition(code):
    code_int = int(code)
    return _weather_codes[code_int]


def get_weather(lat, lon):
    """
    Get weather based on location 
    """
    response = requests.get("https://api.open-meteo.com/v1/forecast",
    {
        "latitude": lat,
        "longitude": lon,
        "current_weather": True
    }, timeout=5)
    data = response.json()
    temp = data["current_weather"]["temperature"]
    condition_code = data["current_weather"]["weathercode"]
    condition = _parse_condition(condition_code)
    return temp, condition
