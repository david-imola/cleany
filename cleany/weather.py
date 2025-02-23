"""
Functions for retrieving weather information.
"""

import requests


_weather_codes = [
    "Cloud development not observed or not observable",
    "Clouds generally dissolving or becoming less developed",
    "State of sky on the whole unchanged",
    "Clouds generally forming or developing",
    "Visibility reduced by smoke, e.g. veldt or forest fires, industrial smoke or volcanic ashes",
    "Haze",
    "Widespread dust in suspension in the air, not raised by wind",
    "Dust or sand raised by wind, but no duststorm or sandstorm",
    "Well developed dust whirl(s), but no duststorm or sandstorm",
    "Duststorm or sandstorm within sight or during the preceding hour",
    "Mist",
    "Patches of shallow fog or ice fog",
    "More or less continuous shallow fog or ice fog",
    "Lightning visible, no thunder heard",
    "Precipitation within sight, not reaching the ground",
    "Precipitation within sight, reaching the ground but distant",
    "Precipitation within sight, near but not at the station",
    "Thunderstorm, but no precipitation at observation time",
    "Squalls at or within sight of the station",
    "Funnel cloud(s) (Tornado or waterspout)",
    "Drizzle (not freezing) or snow grains, not falling as showers",
    "Rain (not freezing)",
    "Snow",
    "Rain and snow or ice pellets",
    "Freezing drizzle or freezing rain",
    "Showers of rain",
    "Showers of snow or rain and snow",
    "Showers of hail or rain and hail",
    "Fog or ice fog",
    "Thunderstorm (with or without precipitation)",
    "Slight or moderate duststorm or sandstorm, decreasing",
    "Slight or moderate duststorm or sandstorm, no change",
    "Slight or moderate duststorm or sandstorm, increasing",
    "Severe duststorm or sandstorm, decreasing",
    "Severe duststorm or sandstorm, no change",
    "Severe duststorm or sandstorm, increasing",
    "Slight or moderate blowing snow, low",
    "Heavy drifting snow",
    "Slight or moderate blowing snow, high",
    "Heavy drifting snow",
    "Fog or ice fog at a distance, but not at the station",
    "Fog or ice fog in patches",
    "Fog or ice fog, sky visible, becoming thinner",
    "Fog or ice fog, sky invisible",
    "Fog or ice fog, sky visible, no change",
    "Fog or ice fog, sky invisible",
    "Fog or ice fog, sky visible, becoming thicker",
    "Fog or ice fog, sky invisible",
    "Fog, depositing rime, sky visible",
    "Fog, depositing rime, sky invisible",
    "Drizzle, not freezing, intermittent, slight",
    "Drizzle, not freezing, continuous",
    "Drizzle, not freezing, intermittent, moderate",
    "Drizzle, not freezing, continuous",
    "Drizzle, not freezing, intermittent, heavy",
    "Drizzle, not freezing, continuous",
    "Drizzle, freezing, slight",
    "Drizzle, freezing, moderate or heavy",
    "Drizzle and rain, slight",
    "Drizzle and rain, moderate or heavy",
    "Rain, not freezing, intermittent, slight",
    "Rain, not freezing, continuous",
    "Rain, not freezing, intermittent, moderate",
    "Rain, not freezing, continuous",
    "Rain, not freezing, intermittent, heavy",
    "Rain, not freezing, continuous",
    "Rain, freezing, slight",
    "Rain, freezing, moderate or heavy",
    "Rain or drizzle and snow, slight",
    "Rain or drizzle and snow, moderate or heavy",
    "Intermittent snowfall, slight",
    "Continuous snowfall",
    "Intermittent snowfall, moderate",
    "Continuous snowfall",
    "Intermittent snowfall, heavy",
    "Continuous snowfall",
    "Diamond dust (with or without fog)",
    "Snow grains (with or without fog)",
    "Isolated star-like snow crystals (with or without fog)",
    "Ice pellets",
    "Rain shower(s), slight",
    "Rain shower(s), moderate or heavy",
    "Rain shower(s), violent",
    "Showers of rain and snow, slight",
    "Showers of rain and snow, moderate or heavy",
    "Snow shower(s), slight",
    "Snow shower(s), moderate or heavy",
    "Showers of snow pellets or small hail, slight",
    "Showers of snow pellets or small hail, moderate or heavy",
    "Showers of hail, not associated with thunder, slight",
    "Showers of hail, not associated with thunder, moderate or heavy",
    "Thunderstorm with slight rain at observation time",
    "Thunderstorm with moderate or heavy rain at observation time",
    "Thunderstorm with slight snow, rain and snow mixed, or hail",
    "Thunderstorm with moderate or heavy snow, rain and snow mixed, or hail",
    "Thunderstorm, slight or moderate, without hail, with rain/snow",
    "Thunderstorm, slight or moderate, with hail",
    "Thunderstorm, heavy, without hail, with rain/snow",
    "Thunderstorm with duststorm or sandstorm",
    "Thunderstorm, heavy, with hail"
]


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
