"""Models for Envisalink."""
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN
from .controller import EnvisalinkController

class EnvisalinkDevice(Entity):
    """Representation of an Envisalink device."""

    def __init__(self, name_suffix, controller):
        """Initialize the device."""
        self._controller = controller
        self._name = f"{controller.alarm_name}_{name_suffix}"

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this WLED device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._controller.unique_id)},
            name=self._controller.alarm_name,
            manufacturer='eyezon',
            model=f'Envisalink {self._controller.version}: {self._controller.panel_type}',
            sw_version=self._controller.controller.firmware_version,
            hw_version='unknown',
            configuration_url=f"http://{self._controller.host}",
        )
