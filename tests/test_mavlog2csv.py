# -*- coding: utf-8 -*-
import contextlib
import csv
import datetime
import inspect
from io import IOBase
from typing import List, Optional
from unittest import mock

import pytest
from pymavlink.DFReader import DFReader
from pymavlink.dialects.v10.ardupilotmega import MAVLink_message

import mavlog2csv


class StubMavlink:
    def __init__(self):
        self.messages: List[MAVLink_message] = []

    def start(self):
        self.msg_queue = iter(self.messages)

    def recv_match(self, blocking, type) -> Optional[MAVLink_message]:
        try:
            return next(self.msg_queue)
        except StopIteration:
            return None


def build_message(message_type, ts: Optional[datetime.datetime] = None, **kwargs):
    ts = ts or datetime.datetime.now().timestamp()
    kwargs.setdefault("_timestamp", ts)
    return type(f"TestMavlinkMessage_{message_type}", (MAVLink_message,), kwargs)(msgId=0, name=message_type)


@pytest.fixture()
def mock_mavlink_stub():
    stub = StubMavlink()
    with mock.patch.object(mavlog2csv, "mavlink_connect", return_value=contextlib.nullcontext(stub)):
        yield stub


@pytest.mark.parametrize(
    ("message", "is_bad"),
    [
        (MAVLink_message(0, "BAD_DATA"), True),
        (MAVLink_message(0, "GPS"), False),
        (None, True),
    ],
)
def test_is_message_bad(message, is_bad):
    assert mavlog2csv.is_message_bad(message) == is_bad


@pytest.mark.parametrize(
    ("cli_column", "expected", "must_fail"),
    [
        ("GPS.Lng", ("GPS", "Lng"), False),
        ("ASPD.Airspeed", ("ASPD", "Airspeed"), False),
        ("GPS", None, True),
        ("", None, True),
    ],
)
def test_parse_cli_column(cli_column, expected, must_fail):
    if must_fail:
        with pytest.raises(ValueError):
            mavlog2csv.parse_cli_column(cli_column)
    else:
        assert mavlog2csv.parse_cli_column(cli_column) == expected


def test_open_output_file(tmp_path):
    file_path = tmp_path / "test.bin"

    ctx = mavlog2csv.open_output(file_path)
    assert hasattr(ctx, "__enter__")
    with ctx as enter_result:
        assert isinstance(enter_result, IOBase)


def test_open_output_no_file():
    ctx = mavlog2csv.open_output()
    assert hasattr(ctx, "__enter__")
    with ctx as enter_result:
        assert isinstance(enter_result, IOBase)


def test_iter_mavlink_messages(mock_mavlink_stub):
    mock_mavlink_stub.messages = [MAVLink_message(0, name="TEST")]
    mock_mavlink_stub.start()

    received_messages = list(mavlog2csv.iter_mavlink_messages(device="test", types={"TEST"}, skip_n_arms=0))

    assert len(received_messages) == 1


def test_iter_mavlink_messages_skip_n_arms(mock_mavlink_stub):
    mock_mavlink_stub.messages = [
        build_message("TEST"),
        build_message("EV", Id=10),
        build_message("TEST"),
    ]
    mock_mavlink_stub.start()

    received_messages = list(mavlog2csv.iter_mavlink_messages(device="test", types={"TEST"}, skip_n_arms=1))

    assert len(received_messages) == 1


@pytest.mark.parametrize(
    ("message", "columns", "row"),
    [
        (
            build_message(
                "TEST",
                TimeUS=1_000_000 * 5,
                col1="test",
                _timestamp=datetime.datetime(2023, 1, 1, 1, 1, 1).timestamp(),
            ),
            ["col1"],
            {
                "TimeUS": 1_000_000 * 5,
                "TimeS": 5.0,
                "TEST.col1": "test",
                "Date": datetime.date(2023, 1, 1).isoformat(),
                "Time": datetime.time(1, 1, 1).isoformat(),
            },
        )
    ],
)
def test_message_to_row(message, columns, row):
    assert mavlog2csv.message_to_row(message, columns) == row


def test_mavlog2csv(mock_mavlink_stub, tmp_path):
    dt = datetime.datetime.now()
    mock_mavlink_stub.messages = [
        build_message("TEST", col1="ignored"),
        build_message("EV", Id=10),
        build_message("OTHER", col1="ignored"),
        build_message("TEST", col1="used", TimeUS=1_000_000 * 5, _timestamp=dt.timestamp()),
    ]
    mock_mavlink_stub.start()

    output_file = tmp_path / "output.csv"

    mavlog2csv.mavlog2csv(
        device="test",
        output=str(output_file),
        columns=["TEST.col1"],
        skip_n_arms=1,
    )

    assert output_file.exists()
    with output_file.open() as csv_file:
        csv_reader = csv.reader(csv_file)
        rows = list(csv_reader)

    assert len(rows) == 2
    assert rows[1] == [
        "5000000",
        "5.0",
        dt.date().isoformat(),
        dt.time().isoformat(),
        "used",
    ]
