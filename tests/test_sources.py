import datetime as dt
from types import SimpleNamespace

from onecut import sources


class FakePath:
    def __init__(self, name: str, stat_result: SimpleNamespace) -> None:
        self.name = name
        self._stat_result = stat_result

    def stat(self) -> SimpleNamespace:
        return self._stat_result


def test_timestamp_prefers_macos_created_time_over_embedded_metadata() -> None:
    created = 1_784_627_612.0
    path = FakePath(
        "CAM_20260721105228_0030_D.MP4",
        SimpleNamespace(st_birthtime=created),
    )
    data = {
        "format": {
            "tags": {
                "creation_time": "2026-07-21T08:52:29.000000Z",
            }
        }
    }

    timestamp, label, source = sources._timestamp(data, path)

    assert timestamp == created
    assert label == dt.datetime.fromtimestamp(created).astimezone().isoformat(timespec="seconds")
    assert source == "created time"


def test_timestamp_uses_metadata_when_created_time_is_unavailable() -> None:
    path = FakePath(
        "CAM_20260721105228_0030_D.MP4",
        SimpleNamespace(st_mtime=1_784_627_612.0),
    )
    data = {
        "format": {
            "tags": {
                "creation_time": "2026-07-21T08:52:29.000000Z",
            }
        }
    }

    timestamp, label, source = sources._timestamp(data, path)

    expected = dt.datetime(2026, 7, 21, 8, 52, 29, tzinfo=dt.timezone.utc).timestamp()
    assert timestamp == expected
    assert label == "2026-07-21T08:52:29.000000Z"
    assert source == "metadata"
