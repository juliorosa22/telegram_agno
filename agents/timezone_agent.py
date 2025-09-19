from agno.agent import Agent
from agno.models.groq import Groq
import os
import asyncio
from datetime import datetime
import pytz
from typing import Tuple, Optional
from agno.tools import tool
from timezonefinder import TimezoneFinder
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

# --- 1. Define the tool as a self-contained function ---
# It should not have `self` or other external dependencies in its signature.
# The necessary clients (geolocator, timezonefinder) are created inside.
@tool
def get_iana_timezone(location_name: str) -> str:
    """
    Finds the official IANA timezone name (e.g., 'America/Sao_Paulo') for a given city or location name.
    This is the primary tool to use.

    Args:
        location_name: The name of the city or location (e.g., "Rio de Janeiro", "Paris", "Tokyo").

    Returns:
        The official IANA timezone name as a string, or "INVALID" if not found.
    """
    try:
        geolocator = Nominatim(user_agent="okanfit_telegram_bot")
        tf = TimezoneFinder()
        
        # Use the geolocator to get coordinates for the location name
        location = geolocator.geocode(location_name, timeout=10)
        if location:
            # Find the timezone using the coordinates
            timezone_name = tf.timezone_at(lng=location.longitude, lat=location.latitude)
            if timezone_name:
                print(f"✅ TimezoneTool: Found '{timezone_name}' for '{location_name}'")
                return timezone_name
        
        print(f"⚠️ TimezoneTool: Could not find a valid timezone for '{location_name}'")
        return "INVALID"
    except (GeocoderTimedOut, GeocoderUnavailable):
        print(f"❌ TimezoneTool: Geocoding service is unavailable.")
        return "INVALID"
    except Exception as e:
        print(f"❌ TimezoneTool: An unexpected error occurred: {e}")
        return "INVALID"

class TimezoneAgent:
    def __init__(self):
        """
        Initializes the TimezoneAgent with tools to find timezone information.
        """
        self.agent = Agent(
            name="TimezoneIdentifier",
            model=Groq(id="llama-3.3-70b-versatile", temperature=0.1),
            # --- 2. Pass the function object, NOT a function call ---
            tools=[get_iana_timezone],
            # --- 3. Update instructions to match the tool name ---
            instructions="""
            You are a timezone expert. Your goal is to identify the user's IANA timezone based on their text input.
            - The user will provide a location in their own language.
            - You MUST use the 'get_iana_timezone' tool to find the official IANA timezone for that location.
            - Once the tool returns a valid IANA name or "INVALID", your job is done.
            - Your final response should ONLY be the IANA name provided by the tool (e.g., "America/Sao_Paulo") or "INVALID". Do not add any other text.
            """
        )
        # --- 4. Remove the geolocator from here, as it's now inside the tool ---

    def _get_utc_offset_string(self, iana_timezone: str) -> Optional[str]:
        """Calculates the current UTC offset string (e.g., UTC-04:00) for a given IANA timezone."""
        try:
            tz = pytz.timezone(iana_timezone)
            now = datetime.now(tz)
            offset = now.utcoffset()
            
            if offset is None:
                return None

            total_seconds = offset.total_seconds()
            sign = '+' if total_seconds >= 0 else '-'
            hours = int(abs(total_seconds) / 3600)
            minutes = int((abs(total_seconds) % 3600) / 60)
            
            return f"UTC{sign}{hours:02d}:{minutes:02d}"
        except pytz.UnknownTimeZoneError:
            return None
    
    
    async def identify_timezone(self, language: str, text_input: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Identifies an IANA timezone and its UTC offset by using an agent with tools.
        The 'language' parameter is no longer needed as the agent handles it.

        Args:
            language: The user's language code (e.g., 'en', 'es', 'pt').
            text_input: The natural language text from the user.

        Returns:
            A tuple containing (iana_name, utc_offset_string), or (None, None) if identification fails.
        """
        # --- 1. Define multilingual prompt templates ---
        prompts = {
            "en": """
            Analyze the user's text and identify the corresponding IANA timezone name.
            Examples:
            - User input: "I'm in new york" -> Your response: America/New_York
            - User input: "My timezone is pacific time" -> Your response: America/Los_Angeles
            - User input: "I live in London" -> Your response: Europe/London
            - User input: "sao paulo" -> Your response: America/Sao_Paulo
            - User input: "CET" -> Your response: Europe/Berlin
            
            User input: "{text_input}"
            Your response:
            """,
            "es": """
            Analiza el texto del usuario e identifica el nombre de la zona horaria IANA correspondiente.
            Ejemplos:
            - Texto del usuario: "estoy en nueva york" -> Tu respuesta: America/New_York
            - Texto del usuario: "mi zona horaria es la del pacífico" -> Tu respuesta: America/Los_Angeles
            - Texto del usuario: "vivo en londres" -> Tu respuesta: Europe/London
            - Texto del usuario: "sao paulo" -> Tu respuesta: America/Sao_Paulo
            - Texto del usuario: "CET" -> Tu respuesta: Europe/Berlin

            Texto del usuario: "{text_input}"
            Tu respuesta:
            """,
            "pt": """
            Analise o texto do usuário e identifique o nome do fuso horário IANA correspondente.
            Exemplos:
            - Texto do usuário: "estou em nova iorque" -> Sua resposta: America/New_York
            - Texto do usuário: "meu fuso é o do pacífico" -> Sua resposta: America/Los_Angeles
            - Texto do usuário: "moro em londres" -> Sua resposta: Europe/London
            - Texto do usuário: "sao paulo" -> Sua resposta: America/Sao_Paulo
            - Texto do usuário: "CET" -> Sua resposta: Europe/Berlin

            Texto do usuário: "{text_input}"
            Sua resposta:
            """
        }

        try:
            # --- 2. Select and format the prompt ---
            prompt_template = prompts.get(language, prompts["en"])
            full_prompt = prompt_template.format(text_input=text_input)

            # --- 3. Use the LLM with the dynamic prompt ---
            response = await asyncio.to_thread(self.agent.run, full_prompt)
            iana_name = response.content.strip()
            print("✅ TimezoneAgent identified:", iana_name)
            if iana_name == "INVALID" or iana_name not in pytz.all_timezones:
                return None, None

            utc_offset = self._get_utc_offset_string(iana_name)
            
            return iana_name, utc_offset
        except Exception as e:
            print(f"❌ Error in tool-based TimezoneAgent: {e}")
            return None, None
