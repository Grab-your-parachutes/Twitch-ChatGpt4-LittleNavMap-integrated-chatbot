# File: littlenavmap_integration.py
# -*- coding: utf-8 -*-
import aiohttp
import logging
import sys
from config import Config

class LittleNavmapIntegration:
    def __init__(self, config: Config):
        self.config = config
        self.base_url = "http://localhost:8965/api"
        self.logger = logging.getLogger('LittleNavmapIntegration')
        
        # Set up detailed logging
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.logger.debug("LittleNavmapIntegration initialized with base_url: %s", self.base_url)

    async def start(self):
        """Initialize the integration."""
        sim_info = await self.get_sim_info()
        if sim_info:
            self.logger.info("Successfully connected to LittleNavMap")
            self.logger.debug(f"Initial sim info: {sim_info}")
        else:
            self.logger.warning("Could not connect to LittleNavMap on startup")

    async def stop(self):
        """Clean up resources."""
        self.logger.info("LittleNavMap integration stopped")

    async def get_sim_info(self):
        """Get current simulation information."""
        return await self._get_data('/sim/info')

    async def get_airport_info(self, ident: str):
        """Get information about a specific airport."""
        return await self._get_data(f'/airport/info?ident={ident}')

    async def get_current_flight_data(self):
        """Get current flight data."""
        sim_info = await self.get_sim_info()
        if sim_info:
            return {
                'aircraft': {
                    'altitude': sim_info.get('indicated_altitude', 0),
                    'speed': sim_info.get('ground_speed', 0) * 3600,  # Convert to km/h
                    'heading': sim_info.get('heading', 0),
                    'latitude': sim_info.get('position', {}).get('lat', 0),
                    'longitude': sim_info.get('position', {}).get('lon', 0),
                    'wind_direction': sim_info.get('wind_direction', 0),
                    'wind_speed': sim_info.get('wind_speed', 0) * 3.6,  # Convert to km/h
                    'on_ground': sim_info.get('on_ground', False)
                }
            }
        return None

    async def _get_data(self, endpoint: str):
        """Helper function to make a request to a specific API endpoint."""
        self.logger.debug(f"Attempting to retrieve data from endpoint: {endpoint}")
        url = f"{self.base_url}{endpoint}"
        self.logger.debug(f"Full URL: {url}")
        
        headers = {
            'User-Agent': 'TwitchBot/1.0',
            'Accept': 'application/json'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    self.logger.debug(f"Response status: {response.status}")
                    self.logger.debug(f"Response headers: {response.headers}")
                    content = await response.text()
                    self.logger.debug(f"Response content: {content}")
                    
                    if response.status == 200:
                        data = await response.json()
                        self.logger.info(f"Successfully retrieved data from {endpoint}")
                        return data
                    else:
                        self.logger.error(f"Failed to retrieve data from {endpoint}. Status code: {response.status}. Content: {content}")
                        return None
        except aiohttp.ClientError as e:
            self.logger.error(f"Connection error while accessing {url}: {str(e)}")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred: {str(e)}")
        return None

    def format_flight_data(self, data):
        """Format flight data for chat display."""
        if not data:
            return "Unable to retrieve flight data."
        
        try:
            # Convert units to aviation standards
            altitude_ft = round(data.get('indicated_altitude', 0))
            altitude_agl_ft = round(data.get('altitude_above_ground', 0) * 3.28084)  # meters to feet
            ground_speed_kts = max(0, round(data.get('ground_speed', 0) * 1.943844))  # m/s to knots
            heading = round(data.get('heading', 0), 1)
            wind_speed_kts = round(data.get('wind_speed', 0) * 1.943844)  # m/s to knots
            wind_direction = round(data.get('wind_direction', 0), 1)
            vertical_speed_fpm = round(data.get('vertical_speed', 0) * 196.85)  # m/s to ft/min
            true_airspeed_kts = max(0, round(data.get('true_airspeed', 0) * 1.943844))  # m/s to knots
            
            # Format position
            lat = data.get('position', {}).get('lat', 0)
            lon = data.get('position', {}).get('lon', 0)
            
            # Determine flight phase
            if altitude_agl_ft < 1:
                phase = "On Ground"
            elif vertical_speed_fpm > 500:
                phase = "Climbing"
            elif vertical_speed_fpm < -500:
                phase = "Descending"
            else:
                phase = "Cruise"
            
            return (
                f"Flight Status Report: Flight Status - {phase} "
                f"Altitude: {altitude_ft:,} ft MSL ({altitude_agl_ft:,} ft Above Ground Level) "
                f"Speed: {ground_speed_kts} knots, Ground speed , {true_airspeed_kts} knots True Airspeed, "
                f"Heading: {heading}°, "
                f"Position: {lat:.4f}°, {lon:.4f}°, "
                f"Wind: {wind_direction}° at {wind_speed_kts} knots, "
                f"Vertical Speed: {vertical_speed_fpm:+,} feet per minute."
            )
        except Exception as e:
            self.logger.error(f"Error formatting flight data: {e}")
            return "Error formatting flight data."

    def get_flight_phase(self, data):
        """Determine the current flight phase."""
        if not data:
            return "Unknown"
            
        try:
            altitude_agl = data.get('altitude_above_ground', 0) * 3.28084  # Convert to feet
            vertical_speed = data.get('vertical_speed', 0) * 196.85  # Convert to ft/min
            ground_speed = data.get('ground_speed', 0) * 1.943844  # Convert to knots
            
            if altitude_agl < 1:
                if ground_speed < 1:
                    return "Parked"
                else:
                    return "Taxiing"
            elif altitude_agl < 50:
                if vertical_speed > 100:
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
            self.logger.error(f"Error determining flight phase: {e}")
            return "Unknown"

    def format_weather_data(self, data):
        """Format weather data for chat display."""
        if not data:
            return "Unable to retrieve weather data."
        
        try:
            # Convert units
            wind_speed_kts = round(data.get('wind_speed', 0) * 1.943844)  # m/s to knots
            wind_direction = round(data.get('wind_direction', 0), 0)
            pressure_inhg = data.get('sea_level_pressure', 0) / 33.8639  # hPa to inHg
            
            return (
                f"Weather Report\n"
                f"Wind: {wind_direction:03.0f}° at {wind_speed_kts} knots\n"
                f"Pressure: {pressure_inhg:.2f} inHg"
            )
        except Exception as e:
            self.logger.error(f"Error formatting weather data: {e}")
            return "Error formatting weather data."
        
    def format_brief_status(self, data):
        """Format a brief status update."""
        if not data:
            return "Unable to retrieve status."
        
        try:
            phase = self.get_flight_phase(data)
            altitude_ft = round(data.get('indicated_altitude', 0))
            ground_speed_kts = max(0, round(data.get('ground_speed', 0) * 1.943844))
            
            return f"{phase}: {altitude_ft:,} ft, {ground_speed_kts} knots"
        except Exception as e:
            self.logger.error(f"Error formatting brief status: {e}")
            return "Error formatting status."

    def format_airport_data(self, data):
        """Format airport data for chat display."""
        if not data:
            return "Unable to retrieve airport data."
        
        try:
            return (
                f"Airport {data.get('ident', 'Unknown')}: "
                f"{data.get('name', 'Unknown')}, "
                f"Elevation: {data.get('elevation', 'Unknown')} feet"
            )
        except Exception as e:
            self.logger.error(f"Error formatting airport data: {e}")
            return "Error formatting airport data."