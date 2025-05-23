import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import EntitySelector
from .const import DOMAIN

# Schema for the user input (IP Address)
STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required("ip_address"): str,
    vol.Optional("temperature_entity"): EntitySelector(
        {"domain": "sensor"}
    )
})

class TesyConvectorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tesy Convector."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            ip_address = user_input["ip_address"]

            valid = await self._test_ip_address(ip_address)
            if valid:
                return self.async_create_entry(title="Tesy Convector", data=user_input)
            else:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def _test_ip_address(self, ip_address):
        """Test if we can connect to the convector with the given IP address."""
        try:
            import socket
            socket.inet_aton(ip_address)
            return True
        except socket.error:
            return False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return TesyConvectorOptionsFlowHandler(config_entry)

class TesyConvectorOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Tesy Convector options flow."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = {
            vol.Required(
                "ip_address",
                default=self.config_entry.options.get("ip_address", self.config_entry.data.get("ip_address"))
            ): str
        }

        temp_entity = self.config_entry.options.get(
            "temperature_entity",
            self.config_entry.data.get("temperature_entity")
        )

        if temp_entity:
            schema[vol.Optional("temperature_entity", default=temp_entity)] = EntitySelector({"domain": "sensor"})
        else:
            schema[vol.Optional("temperature_entity")] = EntitySelector({"domain": "sensor"})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )
