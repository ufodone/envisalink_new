"""Repairs for Z-Wave JS."""

from __future__ import annotations

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, LOGGER


class MigrateUniqueIDFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, data: dict[str, str]) -> None:
        """Initialize."""
        LOGGER.error(f"MigrateUniqueIDFlow: data={data}")
        self.description_placeholders: dict[str, str] = {
            "config_entry_title": data["config_entry_title"],
            "new_unique_id": data["new_unique_id"],
            "old_unique_id": data["old_unique_id"],
        }
        self._config_entry_id: str = data["config_entry_id"]

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            config_entry = self.hass.config_entries.async_get_entry(self._config_entry_id)
            # If config entry was removed, we can ignore the issue.
            if config_entry is not None:
                self.hass.config_entries.async_update_entry(
                    config_entry,
                    unique_id=self.description_placeholders["new_unique_id"],
                )

                await self._async_update_entities()

                self.hass.config_entries.async_schedule_reload(config_entry.entry_id)
            return self.async_create_entry(data={})

        LOGGER.error(f"desc_place: {self.description_placeholders}")
        return self.async_show_form(
            step_id="confirm",
            description_placeholders=self.description_placeholders,
        )

    async def _async_update_entities(self):
        """Update the unique ID on all the entities attached to this config entry and remove
        the subsequently orphaned device.
        """

        old_unique_id = self.description_placeholders["old_unique_id"]
        new_unique_id = self.description_placeholders["new_unique_id"]

        @callback
        def _async_update_unique_id(
            entity_entry: er.RegistryEntry,
        ) -> dict[str, str] | None:
            id_parts = entity_entry.unique_id.split("_")
            if id_parts[0] == old_unique_id:
                id_parts[0] = new_unique_id
                return {"new_unique_id": "_".join(id_parts)}

        await er.async_migrate_entries(
            self.hass, self._config_entry_id, _async_update_unique_id
        )

        dev_reg = dr.async_get(self.hass)
        old_device = dev_reg.async_get_device(identifiers={(DOMAIN, old_unique_id)})
        if old_device:
            dev_reg.async_remove_device(old_device.id)


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str] | None
) -> RepairsFlow:
    """Create fix flow."""

    if issue_id.split(".")[0] == "migrate_unique_id":
        assert data
        return MigrateUniqueIDFlow(data)
    return ConfirmRepairFlow()
