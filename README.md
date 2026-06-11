# Polar integration for Home Assistant

This is a _custom component_ for [Home Assistant](https://www.home-assistant.io/).
The `polar` integration pulls your data from [Polar](https://flow.polar.com) via
the [Polar AccessLink API](https://www.polar.com/accesslink-api/) and exposes it
as sensors — sleep, recovery, heart rate and training load — and, importantly,
**backfills recent history** so you don't only see data starting from the moment
you installed the integration.

## Features

- **OAuth2 setup** against Polar AccessLink, with a **connection test** when you
  add your credentials: it checks connectivity to Polar and that your `Client ID`
  is accepted, logs the result, and reports a clear error up front instead of
  failing later during the OAuth exchange.
- **Rich sensors**: continuous heart rate, heart rate variability, breathing
  rate, deep/light/REM sleep, sleep score, cardio (training) load, daily
  activity, weight and last-exercise stats.
- **History backfill**: imports up to ~28 days of Polar history (and 7 days of
  hourly heart rate) as long-term statistics **on the sensors themselves**, so
  each sensor's *History* page shows the past — including data from before the
  integration was installed.
- **Ready-to-use dashboard** for training + sleep tracking
  ([`polar-dashboard.yaml`](./polar-dashboard.yaml)).

## Installation

### HACS

HACS > Integrations > Explore & Add Repositories > Polar > Install this repository

### Manually

Copy the `custom_components/polar` folder into the config folder.

## Configuration

You need to create a Client in [Polar Access Link](https://admin.polaraccesslink.com)
and set in `Authorization redirect URLs`:

* `https://your_external_access_to_ha`
* `https://your_external_access_to_ha/api/polar_auth` (selected)

To add the Polar integration to your installation, go to Settings >> Devices &
Services in the UI, click the **+ Add Integration** button and select Polar.

### Fields

* `Client ID` and `Client secret`: get credentials from [Polar Access Link](https://admin.polaraccesslink.com).
* `Scan Interval`: interval in minutes between two scans of the Polar API (default: `30`).
* `URL`: URL used to access your Home Assistant (default: your external or internal URL if configured in HA settings).

When you submit your credentials the integration first runs a connection test
(reachability to Polar + that the `Client ID` is accepted) and logs the result,
so a wrong URL, missing connectivity or an invalid client is reported up front
with a clear error instead of failing later during the OAuth exchange.

## Sensors

| Sensor | Description |
| --- | --- |
| `Heart rate` | Latest continuous heart rate sample (min / max / average of the day as attributes) |
| `Heart rate variability` | Average HRV (RMSSD, ms) from the last Nightly Recharge |
| `Breathing rate` | Average breathing rate from the last Nightly Recharge |
| `Deep sleep` / `Light sleep` / `REM sleep` | Sleep-stage durations (selectable unit, plus a human-readable `Xh Ym` `duration` attribute) |
| `Last sleep score` | Sleep score 1–100, with all sleep details as attributes |
| `Last nightly recharge` | Nightly Recharge status, with ANS charge / HRV / breathing as attributes |
| `Cardio load` | Training load, with `strain`, `tolerance`, `cardio_load_ratio`, `cardio_load_status` |
| `Last exercise` | Start time of the last training session, with distance / duration / sport / calories |
| `Last exercise heart rate average` / `… maximum` | Heart rate stats of the last training session |
| `Daily activity Steps` / `Calories` / `Duration` | Daily activity summary |
| `Weight` | Latest weight |

Continuous heart rate and cardio load depend on device support and the user's
Polar consents; when unavailable they simply stay unknown — they never break the
rest of the update.

## History backfill

Home Assistant sensors only build history forward from the moment they start
polling and **cannot** backfill past states. Polar, however, keeps the last
~28 days of nightly/daily data and per-day continuous heart rate samples.

On setup (and once a day afterwards) the integration imports that history as
**long-term statistics attached to the sensors themselves**, so each sensor's
*History* page shows the past — including data from before the integration was
installed:

* sleep stages, sleep score, HRV, breathing rate and cardio load → one point per
  day for the last ~28 days;
* continuous heart rate → hourly min / mean / max for the last 7 days.

The import is best-effort: a metric the device doesn't provide (or a day with no
data) is logged and skipped, never failing the rest of the update. This requires
the `recorder` integration (declared as a dependency).

> Note: only the long-term statistics are backfilled. The instantaneous state
> graph still only moves forward — Home Assistant does not allow inserting past
> raw states.

## Dashboard

[`polar-dashboard.yaml`](./polar-dashboard.yaml) is a ready-to-use Lovelace
dashboard for training + sleep tracking:

* **Today** — a live snapshot (heart rate, HRV, breathing, weight, last night's
  sleep stages and recharge, last workout), a sections view built with the
  native `tile` cards and badges;
* **Sleep** — 28-day history of sleep stages, sleep score, HRV and breathing;
* **Training** — 28-day cardio load and 7-day continuous heart rate, plus the
  live heart rate of the day.

It uses only built-in cards (sections view, `tile`, `statistics-graph`) — no
custom HACS cards required. Paste it into a new dashboard via the raw
configuration editor. The entity ids carry your Polar device name as a prefix
(e.g. `sensor.polar_loop_deep_sleep`); if yours differ, find-replace the prefix
in the editor — see the comments at the top of the file.

## Credits

Thanks to https://github.com/burnnat/ha-polar
