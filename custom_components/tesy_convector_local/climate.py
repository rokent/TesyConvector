import asyncio
import logging
from datetime import timedelta

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode
from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.event import async_track_time_interval

from .tesy_convector import TesyConvector
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Tesy Convector climate entity for a config entry."""
    # Pull data from config entry or options
    ip_address = config_entry.options.get("ip_address", config_entry.data.get("ip_address"))
    temperature_entity = config_entry.options.get("temperature_entity", config_entry.data.get("temperature_entity"))

    convector = TesyConvector(ip_address)

    entity = TesyConvectorClimate(
        convector=convector,
        temperature_entity=temperature_entity,
        unique_id=ip_address
    )

    async_add_entities([entity])

class TesyConvectorClimate(ClimateEntity):
    """Representation of a Tesy Convector as a ClimateEntity."""

    def __init__(self, convector, temperature_entity=None, unique_id=None):
        """Initialize the climate entity."""
        self.convector = convector
        self.temperature_entity = temperature_entity
        self._unique_id = unique_id

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

        self._hvac_mode = HVACMode.OFF
        self._current_temp = None
        self._target_temp = None
        self._remove_update_listener = None

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def device_info(self):
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
        self._remove_update_listener = async_track_time_interval(
            self.hass,
            self.async_update,
            timedelta(seconds=60),
        )

    async def async_update(self, *args):
        """Fetch new state data for this entity."""
        if self.temperature_entity:
            temp_state = self.hass.states.get(self.temperature_entity)
            if temp_state:
                try:
                    self._current_temp = float(temp_state.state)
                except ValueError:
                    _LOGGER.error("Invalid temperature value in %s", self.temperature_entity)
        else:
            status = await self.convector.get_status()
            if "payload" in status and "setTemp" in status["payload"]:
                payload = status["payload"]["setTemp"].get("payload", {})
                self._current_temp = payload.get("temp")

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

            set_temp_payload = status["payload"]["setTemp"].get("payload", {})
            self._target_temp = set_temp_payload.get("temp")
        else:
            _LOGGER.error("Unexpected response structure from Tesy Convector: %s", status)
            self._hvac_mode = HVACMode.OFF
            self._target_temp = None

    @property
    def hvac_mode(self):
        return self._hvac_mode

    @property
    def current_temperature(self):
        return self._current_temp

    @property
    def target_temperature(self):
        return self._target_temp

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.HEAT:
            await self.convector.turn_on()
        elif hvac_mode == HVACMode.OFF:
            await self.convector.turn_off()

        await asyncio.sleep(0.1)

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get("temperature")
        if temp is not None and self._target_temp != temp:
            await self.convector.set_temperature(temp)
            self._target_temp = temp
            await asyncio.sleep(0.1)
