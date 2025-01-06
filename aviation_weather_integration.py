# File: aviation_weather_integration.py
import aiohttp
import logging
import json
from typing import Tuple, Optional, Dict, Any
from config import Config
import backoff
import re

class AviationWeatherIntegration:
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger('AviationWeatherIntegration')
        self.base_url = "https://api.checkwx.com/metar/"  # Updated base URL to CheckWX
        self.session = aiohttp.ClientSession()
        self.checkwx_api_key = self.config.checkwx_api_key

    async def start(self):
        """Initialize the integration."""
        self.logger.info("AviationWeatherIntegration Initialized")

    async def stop(self):
        """Close resources."""
        await self.session.close()
        self.logger.info("AviationWeatherIntegration Stopped")

    @backoff.on_exception(backoff.expo, (aiohttp.ClientError, aiohttp.ClientConnectionError, aiohttp.ServerDisconnectedError, aiohttp.ClientPayloadError, aiohttp.ClientResponseError), max_tries=3)
    async def get_metar(self, icao_code: str) -> Optional[Dict]:
        """Fetch METAR data from CheckWX API."""
        if not self.checkwx_api_key:
            self.logger.error("CheckWX API key is not configured.")
            return None
        
        url = f"{self.base_url}{icao_code}"
        headers = {
            "X-API-Key": self.checkwx_api_key,
            "Accept": "application/json"
        }
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    self.logger.debug(f"Raw METAR data for {icao_code}: {json.dumps(data)}")
                    if data.get('results') > 0:
                        metar_data = data.get('data')[0]
                        self.logger.debug(f"Extracted METAR data: {metar_data}")
                        
                        # Extract ICAO code from the raw text
                        icao_match = re.search(r'([A-Z]{4})\s', metar_data)
                        extracted_icao = icao_match.group(1) if icao_match else icao_code
                        
                        return {"raw_text": metar_data, "icao": extracted_icao}
                    else:
                        self.logger.warning(f"No METAR data found for {icao_code}")
                        return None
                else:
                    content = await response.text()
                    self.logger.error(
                        f"Failed to fetch METAR data for {icao_code}. Status code: {response.status}, Content: {content}"
                    )
                    return None
        except aiohttp.ClientError as e:
            self.logger.error(f"Connection error while accessing {url}: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while fetching METAR: {str(e)}", exc_info=True)
            return None


    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()