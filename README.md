ismatec
=======

Python ≥3.8 driver and command-line tool for Masterflex® Ismatec® Reglo ICC Digital Pumps.

![](https://us.vwr.com/stibo/bigweb/std.lang.all/21/78/38732178.jpg)

Installation
============

```
pip install ismatec
```

Usage
=====

## Command Line

```
$ ismatec /dev/ttyUSB0 --channel 1
$ ismatec <serial-to-ethernet-ip>:<port> --channel 2
```

This will print the current flow rate for the selected channel, using either the serial port or an ethernet-to-serial adapter.

## Python

This uses Python ≥3.5's async/await syntax to asynchronously communicate with a Ismatec® Reglo ICC pump. For example:

```python
import asyncio
from ismatec import Pump

async def get():
    async with Pump('/dev/ttyUSB0') as pump:
        print(await pump.get_pump_version())

asyncio.run(get())
```

Acknowledgements
================

©2022 Alexander Ruddick

[Original project](https://github.com/alexbjorling/lib-maxiv-regloicc) ©2017 Alexander Bjoerling

No affiliation to [the Hein group](https://gitlab.com/heingroup/ismatec). As of 2023, that project appears to have been abandoned.
