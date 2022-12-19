# Polar integration for Home Assistant

This a _custom component_ for [Home Assistant](https://www.home-assistant.io/).
The `polar` integration allows you to get information from [Polar](https://flow.polar.com).

You need to create a Client in [Polar Access Link](https://admin.polaraccesslink.com).
Set `https://your_external_access_to_ha/api/polar_auth` as redirect URL. And get client id and secret.

## Installation

### HACS

HACS > Integrations > Explore & Add Repositories > Polar > Install this repository

### Manually

Copy the `custom_components/polar` folder into the config folder.

## Configuration

To add the Polar integration to your installation, go to Configuration >> Integrations in the UI, click the button with + sign and from the list of integrations select Polar.

## Credits

Thanks to https://github.com/burnnat/ha-polar
