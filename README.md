# envisalink_new

**WORK IN PROGRESS**

Temporary HACS version of envisalink integration while undergoing a refactor.

## Current changes include:

- Full support for UI configuration flow (configuration.yaml to be deprecated)
- Support for multiple envisalink devices
- Entities now have unique IDs allowing configuration/customization via the UI
- Zone bypass switch support for DSC panels
- Auto-discovery of EVL version and panel type (DSC/HONEYWELL)
- New algorithm on for Honeywell systems to better handle zone open/close status
- Refactoring of the underlying pyenvisalink package including
  - Sequential queueing of commands to the EVL including retry on errors (which applicable) and timeouts
  - Ability to query EVL firmware version and MAC address
  - Update of asyncio network handling to use Streams rather than low-level APIs

## Installation

### Install using [HACS](https://hacs.xyz/docs/setup/prerequisites)

You need to add this repository to the custom repository page in HACS before you can install this integration.
To do so first go to the HACS Integrations page. From there click the menu in the top right with the 3 dots.
Use this URL for the repository `https://github.com/ufodone/envisalink_new` and select `integration` for the category. After you add the custom repository, just search for `Envisalink Refactored` in HACS and install it. Installation will complete after you reboot Home Assistant.


## Configuration

### Config flow

Configuration of the integration has been upgraded to use HA's config flow (via the UI). To add an envisalink device, go to `Settings -> Devices & Services`, click `Add Integration` at the bottom left of the screen and search for `envisalink_new`. This will then prompt you for basic information about the EVL device. Newly added is an `Alarm Name` which is used to prefix the entities created for your EVL.

Because it is not possible to discover the number of zones and partitions of the alarm system automatically, it will default to creating no zones and a single partition (1). To adjust the setup to match your system, click the `Configure` button on the newly created device and define the available zones and partitions. The zone and partition list accepts a comma separated list of numerical zones/partitions as well as ranges. For example:

```
1-2,4-8,16-18,20-29
```

Unlike the old configuration.yaml approach, the integration will create its own names for the entities it creates based on the `Alarm Name` setting you provided. These can all be changed using the normal HA method (e.g. find the entity in the UI, click it, go to Settings and make any necessary changes).

### configuration.yaml

This method of configuring the integration is still available but is meant primarily to allow for easy upgrades for people using the original integration. On startup, the integration will look for the presence of the configuration and import it into a config entity. The intent here is that once setup, all your entity names, etc. If you subsequently change the configuration.yaml, the next HA restart will re-sync your changes into the config entity. However, it is recommended that once the initial import has been done and confirmed working that the entries in configuration.yaml are removed.

Because the name of the integration has been changed (for now) to avoid conflict with the official packaged version, you will need to change your `envisalink` heading to `envisalink_new` so that this HACS integration will pick it up.

## Testing Help

These are fairly substantial changes and I only have my own system (EVL4/DSC) and configuration to test against. Key things I'd like to get more testing on are:

- Does it import your configuration.yaml correctly?
- If you don't have any configuration.yaml entries, are you able to successfully add the EVL via the UI?
- Does it auto-detect your EVL version and panel type correctly?
- Do you see your firmware version listed in the device settings?
- Do you see any errors or warnings in the log files?
- If you have any automations, etc. connected to your envisalink, do they still work correctly?
- Generally speaking, does anything look wrong or broken?
