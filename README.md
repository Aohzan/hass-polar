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

The client credentials are checked against Polar before the authorization step, so a wrong `Client ID`/`Client secret` or a connection issue is reported directly in the form.

## Sensors

| Sensor | Description |
| --- | --- |
| `Weight` | Weight of the user |
| `Daily activity Calories` / `Duration` / `Steps` | Last daily activity summary |
| `Last exercise` | Start time of the last exercise, details as attributes |
| `Last exercise heart rate average` / `maximum` | Heart rate of the last exercise |
| `Last sleep score` | Sleep score of the last night, details as attributes |
| `Deep sleep` / `Light sleep` / `REM sleep` | Sleep stage durations of the last night |
| `Last nightly recharge` | Nightly Recharge status, details as attributes |
| `Heart rate variability` / `Breathing rate` | Averages measured during the last Nightly Recharge |
| `Cardio load` | Last computed cardio load, with strain, tolerance and status as attributes |

Cardio load and continuous heart rate depend on the device and on the consents given in Polar Flow: when they are not available, their data is simply missing.

## History

Polar keeps the last 28 days of data, but sensors only record history from the moment they are created. The integration imports this history as long-term statistics, available in the [Statistics graph card](https://www.home-assistant.io/dashboards/statistics-graph/) under the name of the user (statistic ids `polar:<user_id>_<metric>`):

* sleep score, deep/light/REM sleep, Nightly Recharge status, heart rate variability, breathing rate and cardio load: one value per day, updated after each scan;
* continuous heart rate: hourly average, minimum and maximum, updated every hour.

These statistics are separate from the sensors' own statistics, which only start when the sensor is created.

## Credits

Thanks to https://github.com/burnnat/ha-polar
