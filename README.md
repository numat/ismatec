Python ≥3.7 driver and command-line tool for RegloICC pumps.

Installation
============

```
pip install ismatec
```

Usage
=====

### Command Line

```
$ ismatec <serial-to-ethernet-ip> --port <port> --channel 1
$ ismatec /dev/ttyUSB0 --channel 2
```

This will print the current flowrate for the selected channel, using either an
Ethernet-to-serial adapater, or a serial port.

### Python

This uses Python ≥3.5's async/await syntax to asynchronously communicate with
a RegloICC pump. For example:

```python
import asyncio
from ismatec import Pump

async def get():
    async with Pump(('serial-to-ethernet-ip', 23)) as pump:
        print(await pump.get_pump_version())

asyncio.run(get())
```

Acknowledgements
================
Original project located at https://github.com/alexbjorling/lib-maxiv-regloicc.
Copyright (C) 2017 Alexander Bjoerling
Copyright (C) 2022 Alexander Ruddick

No affiliation to the Hein group.  (https://gitlab.com/heingroup/ismatec).
As of 2023 that project appears to be abandoned.
