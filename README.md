# Polar integration for Home Assistant

This a _custom component_ for [Home Assistant](https://www.home-assistant.io/).
The `polar` integration allows you to get information from [Polar](https://flow.polar.com).

You need to create a Client in [Polar Access Link](https://admin.polaraccesslink.com) and set in `Authorization redirect URLs`:

* `https://your_external_access_to_ha`
* `https://your_external_access_to_ha/api/polar_auth` (selected)

## Installation

### HACS

HACS > Integrations > Explore & Add Repositories > Polar > Install this repository

### Manually

Copy the `custom_components/polar` folder into the config folder.

## Configuration

To add the Polar integration to your installation, go to Configuration >> Integrations in the UI, click the button with + sign and from the list of integrations select Polar.

### Fields

* `Client ID` and `Client secret`: get credentials grom [Polar Access Link](https://admin.polaraccesslink.com).
* `Scan Interval` interval in minutes between two scan to Polar API (default: `30`)
* `URL`: URL used to access to your Home-Assistant (default: your external or internal URL if configured in HA settings)

## Credits

Thanks to https://github.com/burnnat/ha-polar
