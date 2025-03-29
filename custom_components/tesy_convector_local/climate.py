import asyncio
import logging
from datetime import timedelta

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode
from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.event import async_track_time_interval

from .tesy_convector import TesyConvector
from .const import DOMAIN  # Ensure you have DOMAIN = "tesy_convector_local" (or similar) in const.py

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Tesy Convector climate entity for a config entry."""
    # Pull data from config entry (this is saved by the config flow)
    ip_address = config_entry.data.get("ip_address")
    temperature_entity = config_entry.data.get("temperature_entity")

    # Initialize the TesyConvector helper (for sending commands to the device)
    convector = TesyConvector(ip_address)

    # Create the climate entity, passing a unique_id so each device is separate
    entity = TesyConvectorClimate(
        convector=convector,
        temperature_entity=temperature_entity,
        unique_id=ip_address  # Using IP address as the unique identifier
    )

    # Register the entity with Home Assistant
    async_add_entities([entity])


class TesyConvectorClimate(ClimateEntity):
    """Representation of a Tesy Convector as a ClimateEntity."""

    def __init__(self, convector, temperature_entity=None, unique_id=None):
        """Initialize the climate entity."""
        self.convector = convector
        self.temperature_entity = temperature_entity

        # Unique ID so each device is recognized as distinct in HA
        self._unique_id = unique_id

        # General climate entity attributes
        self._attr_name = "Tesy Convector"
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE |
            ClimateEntityFeature.TURN_OFF |
            ClimateEntityFeature.TURN_ON
        )
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        self._attr_min_temp = 10
        self._attr_max_temp = 30
        self._attr_target_temperature_step = 1

        # Internal state variables
        self._hvac_mode = HVACMode.OFF
        self._current_temp = None
        self._target_temp = None
        self._remove_update_listener = None

    @property
    def unique_id(self):
        """Return a unique ID for this entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device info so Home Assistant shows separate devices."""
        if self._unique_id is None:
            return None
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": f"Tesy Convector ({self._unique_id})",
            "manufacturer": "Tesy",
            "model": "Convector",
        }

    async def async_added_to_hass(self):
        """Run when entity is added to Home Assistant."""
        # Schedule periodic updates every 10 seconds
        self._remove_update_listener = async_track_time_interval(
            self.hass,
            self.async_update,
            timedelta(seconds=60),
        )

    async def async_update(self, *args):
        """Fetch new state data for this entity."""
        # If the user specified a separate temperature sensor, use that
        if self.temperature_entity:
            temp_state = self.hass.states.get(self.temperature_entity)
            if temp_state:
                try:
                    self._current_temp = float(temp_state.state)
                except ValueError:
                    _LOGGER.error("Invalid temperature value in %s", self.temperature_entity)
        else:
            # Otherwise, get the current temperature from the device
            status = await self.convector.get_status()
            if "payload" in status and "setTemp" in status["payload"]:
                payload = status["payload"]["setTemp"].get("payload", {})
                self._current_temp = payload.get("temp")

        # Fetch the full status again to get mode, target temp, etc.
        status = await self.convector.get_status()
        _LOGGER.debug("Tesy Convector status: %s", status)

        if (
            "payload" in status and
            "onOff" in status["payload"] and
            "status" in status["payload"]["onOff"].get("payload", {})
        ):
            if status["payload"]["onOff"]["payload"]["status"] == "on":
                self._hvac_mode = HVACMode.HEAT
            else:
                self._hvac_mode = HVACMode.OFF

            # Extract target temperature
            set_temp_payload = status["payload"]["setTemp"].get("payload", {})
            self._target_temp = set_temp_payload.get("temp")
        else:
            _LOGGER.error("Unexpected response structure from Tesy Convector: %s", status)
            self._hvac_mode = HVACMode.OFF
            self._target_temp = None

    @property
    def hvac_mode(self):
        """Return the current HVAC mode."""
        return self._hvac_mode

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temp

    @property
    def target_temperature(self):
        """Return the current target temperature."""
        return self._target_temp

    async def async_set_hvac_mode(self, hvac_mode):
        """Set the HVAC mode (on/off)."""
        if hvac_mode == HVACMode.HEAT:
            await self.convector.turn_on()
        elif hvac_mode == HVACMode.OFF:
            await self.convector.turn_off()

        # Give the device a moment to process
        await asyncio.sleep(0.1)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp = kwargs.get("temperature")
        if temp is not None and self._target_temp != temp:
            await self.convector.set_temperature(temp)
            self._target_temp = temp
            await asyncio.sleep(0.1)
