# envisalink_new
WORK IN PROGRESS

Temporary HACS version of envisalink integration while undergoing a refactor.

Current changes include:
* Full support for UI configuration flow (configuration.yaml to be deprecated)
* Support for multiple envisalink devices
* Entities now have unique IDs allowing configuration/customization via the UI
* Zone bypass switch support for DSC panels
* Refactoring of the underlying pyenvisalink package including
  * Sequential queueing of commands to the EVL including retry on errors (which applicable) and timeouts
  * Ability to query EVL firmware version and MAC address
  * Update of asyncio network handling to use Streams rather than low-level APIs
