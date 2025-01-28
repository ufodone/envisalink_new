"""Support for Envisalink panic buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .models import EnvisalinkDevice
from .pyenvisalink.const import PANEL_TYPE_DSC, PANEL_TYPE_HONEYWELL

_panel_buttons = [
    {"type": "Fire", "label": {PANEL_TYPE_DSC: "Fire", PANEL_TYPE_HONEYWELL: "A"}},
    {
        "type": "Ambulance",
        "label": {PANEL_TYPE_DSC: "Ambulance", PANEL_TYPE_HONEYWELL: "B"},
    },
    {"type": "Police", "label": {PANEL_TYPE_DSC: "Police", PANEL_TYPE_HONEYWELL: "C"}},
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the panic buttons."""
    controller = hass.data[DOMAIN][entry.entry_id]
    panel_type = controller.controller.panel_type
    entities = []

    for button_info in _panel_buttons:
        label = button_info["label"].get(panel_type)
        if label:
            button = EnvisalinkPanicButton(
                controller,
                f"{controller.unique_id}_{label}",
                f"Panic {label}",
                button_info["type"],
            )
            entities.append(button)

    async_add_entities(entities)


class EnvisalinkPanicButton(EnvisalinkDevice, ButtonEntity):
    """Representation of a demo button entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _panic_type = None

    def __init__(
        self,
        controller: EnvisalinkController,
        unique_id: str,
        name: str,
        panic_type: str,
    ) -> None:
        """Initialize the panic button entity."""
        self._attr_unique_id = unique_id
        self._panic_type = panic_type
        super().__init__(name, controller, None, None)

    async def async_press(self) -> None:
        """Send out a persistent notification."""
        await self._controller.controller.panic_alarm(self._panic_type)
