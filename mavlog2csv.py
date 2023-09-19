# -*- coding: utf-8 -*-
"""
Used https://github.com/ArduPilot/pymavlink/blob/master/tools/mavlogdump.py for reference.
"""
import argparse
import collections
import contextlib
import csv
import datetime
import logging
import operator
import re
import sys
import textwrap
from typing import IO, Any, ContextManager, Dict, Iterator, List, Optional, Set, Tuple, Union

from pymavlink import mavutil
from pymavlink.CSVReader import CSVReader
from pymavlink.DFReader import DFReader
from pymavlink.dialects.v10.ardupilotmega import MAVLink_message
from pymavlink.mavutil import mavserial


logger = logging.getLogger(__name__)


def is_message_bad(message: Optional[MAVLink_message]) -> bool:
    """Check if message is bad and work working with"""
    return bool(message is None or (message and message.get_type() == "BAD_DATA"))


@contextlib.contextmanager
def mavlink_connect(device: str) -> Union[mavserial, DFReader, CSVReader]:
    """
    Create mavlink connection to a device. Device can be anything from comport, to .bin or .log ardupilot telemetry log file.
    Will close the connection once context is exited
    """
    conn = mavutil.mavlink_connection(device)
    logger.debug(f"Connecting to {device}")
    yield conn
    logger.debug(f"Closing connection to {device}")
    conn.close()


def parse_cli_column(cli_col: str) -> Tuple[str, str]:
    """
    Parse CLI provided column into message type and column name parts.
    """
    match = re.match("(?P<message_type>\w+)\.(?P<column>\w+)", cli_col)
    if not match:
        raise ValueError(
            f"""\
            Specified column is not correct format:
            Column "{cli_col}" must be <Message type>.<Column>.
            For example: GPS.Lat
        """
        )
    return match.group(1), match.group(2)


def open_output(output: Optional[str] = None) -> ContextManager[IO]:
    """
    Either opens a file `output` for writing or returns STDOUT stream"""
    if output:
        return open(output, "w", newline="")
    else:
        return contextlib.nullcontext(sys.stdout)


def iter_mavlink_messages(device: str, types: Set[str], skip_n_arms: int = 0) -> Iterator[MAVLink_message]:
    """
    Return iterator over mavlink messages of `types` from `device`.
    If skip_n_arms is not zero, will return messages only after skip_n_arms ARM messages has been seen.
    """
    types = types.copy()
    types.add("EV")  # EV are events like ARM (id=10) or DISARM (id=11)
    n_message = 0
    n_armed = 0
    with mavlink_connect(device) as mav_conn:
        while True:
            message: Optional[MAVLink_message] = mav_conn.recv_match(blocking=False, type=types)
            n_message += 1

            if message is None:
                logger.debug(f"Stopping processing at {n_message} message")
                break

            if is_message_bad(message):
                continue

            if message.get_type() == "EV" and message.Id == 10:  # arm
                logger.debug(f"Found ARM event: {message}")
                n_armed += 1

            if n_armed < skip_n_arms or message.get_type() == "EV":
                continue

            yield message


def message_to_row(message: MAVLink_message, columns: List[str]) -> Dict[str, Any]:
    """Convert mavlink message to output row"""
    row: Dict[str, Any] = {}

    row["TimeUS"] = message.TimeUS
    row["TimeS"] = round(message.TimeUS / 1_000_000, 2)
    dt = datetime.datetime.fromtimestamp(message._timestamp)
    row["Date"] = dt.date().isoformat()
    row["Time"] = dt.time().isoformat()

    for col in columns:
        col_value = getattr(message, col, None) or ""  # Place for improvement
        row[f"{message.get_type()}.{col}"] = col_value

    return row


def mavlog2csv(device: str, columns: List[str], output: Optional[str] = None, skip_n_arms: int = 0):
    """
    Convert ardupilot telemetry log into csv with selected columns.
    Specify the input file (.bin telemetry log), some desired telemetry columns (like GPS.Lat), and observe the magic.
    You can find message types and their column reference here: https://ardupilot.org/copter/docs/logmessages.html.
    """
    parsed_columns: List[Tuple[str, str]] = list(map(parse_cli_column, columns))

    # Collects all required message types like {'GPS', 'ATT', 'ASPD'}
    # Used to filter mavlink messages
    message_type_filter: Set[str] = set(map(operator.itemgetter(0), parsed_columns))

    # Collects a mapping message type -> columns
    # Used to quickly extract required columns from message
    message_type_columns: Dict[str, List[str]] = collections.defaultdict(list)
    for message_type, column in parsed_columns:
        message_type_columns[message_type].append(column)

    header = [
        "TimeUS",  # Original time in US after boot
        "TimeS",  # Seconds after boot
        "Date",  # Calculated date of the event
        "Time",  # Calculated time of the event,
        *columns,  # User specified columns
    ]

    with open_output(output) as output_file:
        csv_writer = csv.DictWriter(
            output_file,
            fieldnames=header,
            delimiter=",",
            quotechar='"',
            quoting=csv.QUOTE_ALL,
        )
        csv_writer.writeheader()
        for message in iter_mavlink_messages(device=device, types=message_type_filter, skip_n_arms=skip_n_arms):
            message_type = message.get_type()
            if message_type in message_type_columns:
                row = message_to_row(message, message_type_columns[message_type])
                csv_writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(mavlog2csv.__doc__),  # type: ignore
        epilog=textwrap.dedent(
            """\
            Example usage:

            # Output GPS Longitude and latitude and airspeed sensor readings
            python mavlog2csv.py -c GPS.Lng -c GPS.Lat -c ARSP.Airspeed -o output.csv "2023-09-17 13-34-16.bin"

            # Redirecting stdout into a file on windows. Not recommended, use -o instead.
            python mavlog2csv.py -c GPS.Lng "2023-09-17 13-34-16.bin" 1> output.csv
        """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("input", help="Input file name.")
    parser.add_argument(
        "-o",
        "--output",
        help="Output file name. If not set, script will output into stdout.",
    )
    parser.add_argument(
        "-c",
        "--col",
        action="append",
        required=True,
        help="Specify telemetry columns to output. Format: <Message type>.<Column>. For example: GPS.Lng",
    )
    parser.add_argument(
        "--skip-n-arms",
        type=int,
        default=0,
        help="If there are multiple arm events in the log, skip this number of arms before writing any rows at all. "
        "If you setup to log only after autopilot was armed, then first arm event wont be stored in the log.",
    )

    args = parser.parse_args()

    mavlog2csv(
        device=args.input,
        columns=args.col,
        skip_n_arms=args.skip_n_arms,
        output=args.output,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
    main()
