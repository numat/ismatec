"""Python driver for Ismatec Reglo ICC peristaltic pump.

Distributed under the GNU General Public License v3
Copyright (C) 2022 NuMat Technologies
"""
from ismatec.driver import Pump


def command_line(args=None):
    """Command-line tool for reading Ismatec Reglo ICC pumps."""
    import argparse
    import asyncio
    import json

    parser = argparse.ArgumentParser(description="Control a RegloICC pump"
                                     "from the command line.")
    parser.add_argument('address', nargs='?', default='/dev/ttyUSB0', help="The "
                        "target serial port or TCP address:port. Default "
                        "'/dev/ttyUSB0'.")
    parser.add_argument('--channel', '-c', default=None, type=int,
                        help="Specify channel in case of multi-channel pump.")
    args = parser.parse_args(args)

    async def run():
        async with Pump(address=(args.address), timeout=.2) as pump:
            d = await pump.get_flow_rate(args.channel)
            print(json.dumps(d, indent=4))

    loop = asyncio.new_event_loop()
    loop.run_until_complete(run())
    loop.close()
    return


if __name__ == '__main__':
    command_line()
