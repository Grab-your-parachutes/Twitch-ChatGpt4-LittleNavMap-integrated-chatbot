# File: littlenavmap_integration.py
# -*- coding: utf-8 -*-
import asyncio
import aiohttp
import logging
import sys
from src.config import Config
import backoff
import aiohttp
import json
import re
from typing import Tuple, Optional, Dict, Any
from urllib.parse import quote

class LittleNavmapIntegration:
    def __init__(self, config):
        self.config = config
        self.base_url = self.config.littlenavmap.BASE_URL
        self.api_base_url = f"{self.config.littlenavmap.BASE_URL}/api" # Corrected base URL
        self.logger = logging.getLogger("LittleNavmapIntegration")
        self.openweathermap_api_key = self.config.openweathermap_api_key
        self.session = aiohttp.ClientSession()
        
        # Set up detailed logging
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.logger.debug("LittleNavmapIntegration initialized with base_url: %s", self.base_url)
        self.session = aiohttp.ClientSession()

    async def start(self):
        """Initialize the integration."""
        try:
            sim_info = await self.get_sim_info()
            if sim_info:
                self.logger.info("Successfully connected to LittleNavMap")
                self.logger.debug(f"Initial sim info: {sim_info}")
            else:
                self.logger.warning("Could not connect to LittleNavMap on startup")
        except Exception as e:
            self.logger.error(f"Error during startup: {e}", exc_info=True)

    async def stop(self):
        """Stop the integration and cleanup."""
        if not self.session.closed:
            await self.session.close()
        self.logger.info("LittleNavMap integration stopped")

    @backoff.on_exception(backoff.expo, aiohttp.ClientError, max_tries=3)
    async def get_sim_info(self):
        """Retrieve simulation information from LittleNavMap."""
        endpoint = f"{self.base_url}/sim/info"
        try:
            async with self.session.get(endpoint) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    content = await response.text()
                    self.logger.error(f"Failed to get sim info. Status: {response.status}, Content: {content}")
                    return None
        except aiohttp.ClientError as e:
            self.logger.error(f"Connection error fetching sim info: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error fetching simulation info: {e}", exc_info=True)
            return None

    @backoff.on_exception(backoff.expo, aiohttp.ClientError, max_tries=3)
    async def get_airport_info(self, ident: str):
        """Get information about a specific airport."""
        return await self._get_data(f'/airport/info', params={"ident": ident.lower()})

    async def get_current_flight_data(self):
        """Get current flight data."""
        sim_info = await self.get_sim_info()
        if sim_info:
            return {
                'aircraft': {
                    'altitude': sim_info.get('indicated_altitude', 0),
                    'speed': self._convert_ms_to_kmh(sim_info.get('ground_speed', 0)),
                    'heading': sim_info.get('heading', 0),
                    'latitude': sim_info.get('position', {}).get('lat', 0),
                    'longitude': sim_info.get('position', {}).get('lon', 0),
                    'wind_direction': sim_info.get('wind_direction', 0),
                    'wind_speed': self._convert_ms_to_kmh(sim_info.get('wind_speed', 0)),
                    'on_ground': sim_info.get('on_ground', False)
                }
            }
        return None

    async def _get_data(self, endpoint: str, params: Optional[Dict] = None):
        """Helper function to make a request to a specific API endpoint."""
        self.logger.debug(f"Attempting to retrieve data from endpoint: {endpoint}")
        url = f"{self.api_base_url}{endpoint[1:]}" # Removed leading slash from endpoint
        self.logger.debug(f"Full URL: {url}")
        
        headers = {
            'User-Agent': 'TwitchBot/1.0',
            'Accept': 'application/json'
        }
        
        try:
            async with self.session.get(url, headers=headers, params=params) as response:
                self.logger.debug(f"Response status: {response.status}")
                self.logger.debug(f"Response headers: {response.headers}")
                self.logger.debug(f"Request URL: {response.request_info.url}") # Log the full URL
                content = await response.text()
                self.logger.debug(f"Response content: {content}")
                
                if response.status == 200:
                    data = await response.json()
                    self.logger.info(f"Successfully retrieved data from {endpoint}")
                    return data
                elif response.status == 404:
                    self.logger.error(f"Failed to retrieve data from {endpoint}. Status code: {response.status}. Content: {content}. Check Little Navmap web server and API path.")
                    return None
                elif response.status >= 500:
                     self.logger.error(f"Server error when accessing {url}. Status code: {response.status}. Content: {content}")
                     raise aiohttp.ClientError(f"Server error when accessing {url}. Status code: {response.status}")
                else:
                    self.logger.error(f"Failed to retrieve data from {endpoint}. Status code: {response.status}. Content: {content}")
                    return None
        except aiohttp.ClientError as e:
            self.logger.error(f"Connection error while accessing {url}: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"An unexpected error occurred: {str(e)}", exc_info=True)
            return None

    async def _fetch_real_world_weather(self, latitude: float, longitude: float) -> Optional[dict]:
        """Fetch real-world weather data using OpenWeatherMap API."""
        api_key = self.config.openweathermap_api_key
        if not api_key:
            self.logger.warning("OpenWeatherMap API key not configured.")
            return None
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={latitude}&lon={longitude}&appid={api_key}&units=metric"
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    self.logger.debug(f"Raw OpenWeatherMap data: {json.dumps(data)}")
                    return data
                else:
                    content = await response.text()
                    self.logger.error(f"Failed to fetch real-world weather data. Status code: {response.status}. Content: {content}")
                    return None
        except aiohttp.ClientError as e:
            self.logger.error(f"Connection error while accessing OpenWeatherMap: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while fetching real-world weather: {str(e)}", exc_info=True)
            return None
            
    async def _fetch_nearest_airport(self, lat: float, lon: float) -> Optional[str]:
        """Fetch the nearest airport ICAO code from Little Navmap."""
        try:
            nearest_airport_data = await self._get_data('/nearest_airport', params={"lat": lat, "lon": lon})
            if nearest_airport_data:
                icao_code = nearest_airport_data.get("icao")
                if icao_code:
                    self.logger.info(f"Nearest airport ICAO: {icao_code}")
                    return icao_code
                else:
                    self.logger.warning("Nearest airport data doesn't contain ICAO code.")
                    return None  # Or handle this case differently, perhaps return ident
            return None
        except Exception as e:
            self.logger.error(f"Error fetching nearest airport: {e}", exc_info=True)
            return None

    def _convert_ms_to_kmh(self, speed_ms: float) -> float:
        """Convert speed from meters per second to kilometers per hour."""
        return speed_ms * 3.6

    def _convert_ms_to_knots(self, speed_ms: float) -> float:
        """Convert speed from meters per second to knots."""
        return speed_ms * 1.943844

    def _convert_meters_to_feet(self, meters: float) -> float:
        """Convert meters to feet."""
        return meters * 3.28084

    def _convert_meters_per_second_to_feet_per_minute(self, speed_ms: float) -> float:
        """Convert speed from meters per second to feet per minute."""
        return speed_ms * 196.85

    def _spell_out_number(self, number: float) -> str:
        """Spell out a number for TTS using aviation phrasing."""
        if number < 0:
            return f"minus {self._spell_out_number(abs(number))}"
        
        parts = str(number).split('.')
        integer_part = parts[0]
        decimal_part = parts[1] if len(parts) > 1 else ""
        
        words = []
        for digit in integer_part:
            if digit == '0':
                words.append("zero")
            elif digit == '1':
                words.append("one")
            elif digit == '2':
                words.append("two")
            elif digit == '3':
                words.append("tree")  # Corrected spelling
            elif digit == '4':
                words.append("four")
            elif digit == '5':
                words.append("fife")  # Corrected spelling
            elif digit == '6':
                words.append("six")
            elif digit == '7':
                words.append("seven")
            elif digit == '8':
                words.append("eight")
            elif digit == '9':
                words.append("niner")  # Corrected spelling
        
        if decimal_part:
            words.append("point")
            for digit in decimal_part:
                if digit == '0':
                    words.append("zero")
                elif digit == '1':
                    words.append("one")
                elif digit == '2':
                    words.append("two")
                elif digit == '3':
                    words.append("tree")  # Corrected spelling
                elif digit == '4':
                    words.append("four")
                elif digit == '5':
                    words.append("fife")  # Corrected spelling
                elif digit == '6':
                    words.append("six")
                elif digit == '7':
                    words.append("seven")
                elif digit == '8':
                    words.append("eight")
                elif digit == '9':
                    words.append("niner")  # Corrected spelling
        return " ".join(words)

    async def format_flight_data(self, data: Dict[str, any]) -> str:
        """Format flight data for chat display."""
        if not data:
            return "Unable to retrieve flight data."

        try:
            # Validate data and provide fallbacks
            altitude_ft = round(self._convert_meters_to_feet(data.get('indicated_altitude', 0) or 0))
            ground_speed_kts = max(0, round(self._convert_ms_to_knots(data.get('ground_speed', 0) or 0)))
            heading = round(data.get('heading', 0) or 0, 1)
            lat = data.get('position', {}).get('lat', 0) or 0
            lon = data.get('position', {}).get('lon', 0) or 0
            wind_speed_kts = round(self._convert_ms_to_knots(data.get('wind_speed', 0) or 0))
            wind_direction = round(data.get('wind_direction', 0) or 0)

            # Determine flight phase
            phase = self.get_flight_phase(data)

            # Concurrent API calls
            nearest_airport_task = asyncio.create_task(self._fetch_nearest_airport(lat, lon))
            real_weather_task = asyncio.create_task(self._fetch_real_world_weather(lat, lon))

            nearest_icao, real_weather = await asyncio.gather(nearest_airport_task, real_weather_task)
            
            airport_message = "Unknown"
            if nearest_icao:
                airport_info_task = asyncio.create_task(self.get_airport_info(nearest_icao))
                airport_info = await airport_info_task
                if airport_info:
                    airport_message = self.format_airport_data(airport_info)
                else:
                    airport_message = "No airport information found."

            airport_info = f"Nearest Airport: {airport_message}" if nearest_icao else "Airport: Unknown."

            real_weather_info = ""
            if real_weather:
                real_temp = real_weather.get("main", {}).get("temp")
                real_wind_dir = real_weather.get("wind", {}).get("deg")
                real_wind_speed = round(real_weather.get("wind", {}).get("speed", 0) * 1.943844)
                real_weather_info = (
                    f" : Real-World Weather: {real_temp} degrees centigrade.  : Wind {real_wind_dir} degrees at {real_wind_speed} knots."
                )


            # Build the response message
            return (
                f"Flight Status - {phase} : "
                f"Altitude is {altitude_ft:,} feet : "
                f"Speed currently {ground_speed_kts} knots. : "
                f"Heading is {heading} degrees. "
                f"{airport_info}"
                f"{real_weather_info}"
            )

        except Exception as e:
            self.logger.error(f"Error formatting flight data: {e}", exc_info=True)
            return "Error formatting flight data. Check logs for details."

    async def stop(self):
        """Close the session properly during shutdown."""
        if not self.session.closed:
            await self.session.close()
        self.logger.info("LittleNavMap integration stopped")

    def get_flight_phase(self, data):
        """Determine the current flight phase."""
        try:
            altitude_agl = self._convert_meters_to_feet(data.get('altitude_above_ground', 0))
            vertical_speed = self._convert_meters_per_second_to_feet_per_minute(data.get('vertical_speed', 0))
            ground_speed = self._convert_ms_to_knots(data.get('ground_speed', 0))

            if altitude_agl < 50:
                if ground_speed < 1:
                    return "Parked"
                elif vertical_speed > 100:
                    return "Taking Off"
                elif vertical_speed < -100:
                    return "Landing"
                else:
                    return "Ground Roll"
            else:
                if vertical_speed > 500:
                    return "Climbing"
                elif vertical_speed < -500:
                    return "Descending"
                else:
                    return "Cruise"
        except Exception as e:
            self.logger.error(f"Error determining flight phase: {e}", exc_info=True)
            return "Unknown"

    def _convert_meters_to_feet(self, meters: float) -> float:
        """Convert meters to feet."""
        return meters * 3.28084

    def _convert_ms_to_knots(self, speed_ms: float) -> float:
        """Convert speed from meters per second to knots."""
        return speed_ms * 1.943844

    def _convert_meters_per_second_to_feet_per_minute(self, speed_ms: float) -> float:
        """Convert speed from meters per second to feet per minute."""
        return speed_ms * 196.85
        
    def format_brief_status(self, data):
        """Format a brief status update."""
        if not data:
            return "Unable to retrieve status."
        
        try:
            phase = self.get_flight_phase(data)
            altitude_ft = round(data.get('indicated_altitude', 0))
            ground_speed_kts = max(0, round(self._convert_ms_to_knots(data.get('ground_speed', 0))))
            
            return f"{phase}: {altitude_ft:,} ft, {ground_speed_kts} knots"
        except Exception as e:
            self.logger.error(f"Error formatting brief status: {e}", exc_info=True)
            return "Error formatting status."

    def format_airport_data(self, data):
        """Format airport data for chat display."""
        if not data:
            return "Unable to retrieve airport data."
        
        try:
            
            name = data.get('name', 'Unknown')
            ident = data.get('ident', 'Unknown')
            elevation = data.get('elevation', 'Unknown')
            
            runways = data.get('runways', [])
            runway_info = ""
            if runways:
                runway_details = [f"{r.get('designator', 'Unknown')}: {r.get('surface', 'Unknown')}, {r.get('length', 'Unknown')}ft, HDG {r.get('longestRunwayHeading', 'Unknown')}" for r in runways]
                runway_info = f" : Runways: {', '.join(runway_details)}."

            atis = ""
            if data.get('com'):
               if data['com'].get('ATIS:'):
                   atis = f" : ATIS {data['com'].get('ATIS:')}"
            tower = ""
            if data.get('com'):
              if data['com'].get('Tower:'):
                 tower = f" : Tower {data['com'].get('Tower:')}"
            
            
            return (
                f"Airport {ident}: {name}. "
                f"Elevation: {elevation} feet."
                 f"{runway_info}"
                 f"{atis}"
                 f"{tower}"
            )
        except Exception as e:
            self.logger.error(f"Error formatting airport data: {e}", exc_info=True)
            return "Error formatting airport data."

    async def format_weather_data(self, data: Dict[str, Any]) -> str:
        """Format weather data for chat display."""
        try:
            if not data:
                return "No weather data available."
                
            wind_direction = round(data.get('wind_direction', 0))
            wind_speed_kts = round(self._convert_ms_to_knots(data.get('wind_speed', 0)))

            return f"Wind {wind_direction} degrees at {wind_speed_kts} knots"
        except Exception as e:
             self.logger.error(f"Error formatting weather data: {e}", exc_info=True)
             return "Error formatting weather data"