"""Python driver for Ismatec RegloICC peristaltic pump.

Distributed under the GNU General Public License v3
Copyright (C) 2022 NuMat Technologies
"""
from ismatec.driver import Pump


def command_line(args=None):
    """CLI interface, accessible when installed through pip."""
    import argparse
    import asyncio
    import json

    parser = argparse.ArgumentParser(description="Control a RegloICC pump"
                                     "from the command line.")
    parser.add_argument('address', nargs='?', default='/dev/ttyUSB0', help="The "
                        "target serial port or TCP address. Default "
                        "'/dev/ttyUSB0'.")
    parser.add_argument('-p', '--port', help="The port of the pump (default 23)",
                        type=int, default=23)
    parser.add_argument('--channel', '-c', default=None, type=int,
                        help="Specify channel in case of multiple-channel pump.")
    args = parser.parse_args(args)

    async def run():
        async with Pump(address=(args.address, args.port), timeout=.2) as pump:
            d = await pump.get_flowrate(args.channel)
            print(json.dumps(d, indent=4))

    loop = asyncio.new_event_loop()
    loop.run_until_complete(run())
    loop.close()
    return


if __name__ == '__main__':
    command_line()
