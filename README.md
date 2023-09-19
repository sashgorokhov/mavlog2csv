# mavlog2csv

[![Test and build](https://github.com/sashgorokhov/mavlog2csv/actions/workflows/test_and_build.yml/badge.svg?branch=main)](https://github.com/sashgorokhov/mavlog2csv/actions/workflows/test_and_build.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
![GitHub last commit (branch)](https://img.shields.io/github/last-commit/sashgorokhov/mavlog2csv/main)

Simple python script that converts ardupilot log into csv. You can specify required telemetry values.
Tested with `.bin` files, will most probably work with `.log` files.
You can even try to specify linux device or comport!

> Mission planner telemetry logs are stored in `Documents\Mission Planner\logs`

I used https://github.com/ArduPilot/pymavlink/blob/master/tools/mavlogdump.py as reference on how to work with telemetry log files.

This script is fully typed and tested. This repository has pre-commit hooks setup and and github actions CI, which builds windows `.exe` on every commit into `main`.

## Usage
Always refer to `--help`.

```text
usage: mavlog2csv.py [-h] [-o OUTPUT] -c COL [--skip-n-arms SKIP_N_ARMS] input

positional arguments:
  input                 Input file name.

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        Output file name. If not set, script will output into stdout.
  -c COL, --col COL     Specify telemetry columns to output. Format: <Message type>.<Column>. For example: GPS.Lng
  --skip-n-arms SKIP_N_ARMS
                        If there are multiple arm events in the log, skip this number of arms before writing any rows at all. If you setup to log only after autopilot was armed, then first arm event wont be stored in the log.
```

### Examples

```shell
python mavlog2csv.py -c GPS.Lat -c GPS.Lng "log.bin"

"TimeUS","TimeS","Date","Time","GPS.Lat","GPS.Lng"
"1411152456","1411.15","2023-09-17","13:54:04.960011","30.532045399999998","-97.6290581"
...
```

Output GPS Longitude and latitude and airspeed sensor readings
```shell
python mavlog2csv.py -c GPS.Lng -c GPS.Lat -c ARSP.Airspeed -o output.csv "2023-09-17 13-34-16.bin"
```

This snippet I find especially useful
```shell
mavlog2csv.exe -c GPS.Lat -c GPS.Lng -c ARSP.Airspeed -c POS.RelHomeAlt -c ATT.Roll -c ATT.Pitch -c ATT.Yaw -c BAT.Volt -c BAT.Cur -c GPS.GCrs -c GPS.VZ -c AETR.Thr -o "C:\Users\Alexander\Desktop\parsed.csv" "C:\Users\Alexander\Documents\Mission Planner\logs\FIXED_WING\1\2023-09-17 13-34-16.bin"
```

## Installation

For windows users, this repository offers an all-in-one `.exe`. You can download it [here](https://github.com/sashgorokhov/mavlog2csv/releases/download/latest/mavlog2csv.exe).

Usage
```shell
mavlog2csv.exe --help
```

### Feeling brave?
```shell
pip install pip install https://github.com/sashgorokhov/mavlog2csv/archive/refs/heads/main.zip
mavlog2csv --help
```
