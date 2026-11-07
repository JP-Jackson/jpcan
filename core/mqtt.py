"""MQTT bus between the core service and its clients (status screen, GaugeWorks,
later Node-RED / Home Assistant / phone page).

Topics (prefix `jpcan/`):
  v/<key>          retained    live value {"v": float|null, "u": units, "t": ts, "e": err}
  meta             retained    profile, VIN, channel info, layouts, shift
  status           retained    state, hint lines, rate, guard counters; LWT = offline
  fuel/history     retained    fill-up history, lifetime stats, correction factor
  cmd/trip_reset   reset trip distance / fuel / trip average
  cmd/fillup       {"gallons": 18.2, "price": 3.459} log a fill-up (validated)
                   These two are the ONLY inputs the core accepts. Nothing from MQTT
                   ever reaches the adapter: the core subscribes to nothing else.

paho-mqtt is EPL-2.0 / EDL-1.0 dual licensed (EDL = BSD-3); not GPL.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Callable

from .bus import Bus, Reading

PREFIX = "jpcan"
T_VALUE = f"{PREFIX}/v/"
T_META = f"{PREFIX}/meta"
T_STATUS = f"{PREFIX}/status"
T_TRIP_RESET = f"{PREFIX}/cmd/trip_reset"
T_FILLUP = f"{PREFIX}/cmd/fillup"
T_FUEL = f"{PREFIX}/fuel/history"
CORE_SUBSCRIPTIONS = (T_TRIP_RESET, T_FILLUP)  # allowlist; see module docstring
OFFLINE = json.dumps({"state": "offline", "lines": ["JpCAN core", "not running"]})


def encode_reading(r: Reading) -> str:
    return json.dumps({"v": r.value, "u": r.units, "t": round(r.ts, 3), "e": r.error})


def decode_reading(key: str, payload: bytes) -> Reading:
    d = json.loads(payload)
    return Reading(key, d.get("v"), d.get("u", ""), d.get("t", time.time()), d.get("e", ""))


class LocalSink:
    """In-process stand-in for MQTT (laptop sim, tests). Also usable as a Feed."""

    def __init__(self, bus: Bus):
        self.bus = bus
        self.meta: dict = {}
        self.status: dict = {}
        self.fuel: dict = {}
        self.connected = True

    def publish_meta(self, meta: dict) -> None:
        self.meta = meta

    def publish_fuel(self, history: dict) -> None:
        self.fuel = history

    def publish_status(self, status: dict) -> None:
        self.status = status

    def close(self) -> None:
        self.status = json.loads(OFFLINE)


def _client(client_id: str):
    import paho.mqtt.client as mqtt

    return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)


class MqttPublisher:
    """Core side: forwards bus readings, meta and status to the broker."""

    def __init__(self, bus: Bus, host: str = "localhost", port: int = 1883,
                 on_trip_reset: Callable[[], None] | None = None,
                 on_fillup: Callable[..., object] | None = None):
        self.bus = bus
        self._on_fillup = on_fillup
        self.fuel: dict = {}
        self.meta: dict = {}
        self.status: dict = {}
        self._on_trip_reset = on_trip_reset
        self.c = _client("jpcan-core")
        self.c.will_set(T_STATUS, OFFLINE, qos=1, retain=True)
        self.c.on_connect = self._on_connect
        self.c.on_message = self._on_message
        self.c.connect_async(host, port, keepalive=30)
        self.c.loop_start()
        bus.subscribe(self.on_reading)

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        for t in CORE_SUBSCRIPTIONS:
            client.subscribe(t, qos=1)
        # (Re)connected: re-publish retained state. Readings published while
        # disconnected were dropped by paho (QoS 0), e.g. read-once odometer.
        if self.meta:
            self.publish_meta(self.meta)
        if self.status:
            self.publish_status(self.status)
        if self.fuel:
            self.publish_fuel(self.fuel)
        for r in self.bus.latest().values():
            self.on_reading(r)

    def _on_message(self, client, userdata, msg):
        if msg.topic == T_TRIP_RESET and self._on_trip_reset:
            self._on_trip_reset()
        elif msg.topic == T_FILLUP and self._on_fillup:
            try:
                d = json.loads(msg.payload)
                self._on_fillup(float(d["gallons"]),
                                None if d.get("price") in (None, "") else float(d["price"]))
            except (ValueError, TypeError, KeyError):
                pass  # ignore garbage; FuelBook also validates ranges

    def on_reading(self, r: Reading) -> None:
        # Retained so late subscribers (screen restart, phone page) get every
        # value at once, including read-once PIDs like the odometer. Staleness
        # is visible via the timestamp and the retained status/LWT.
        self.c.publish(T_VALUE + r.key, encode_reading(r), qos=0, retain=True)

    def publish_meta(self, meta: dict) -> None:
        self.meta = meta
        self.c.publish(T_META, json.dumps(meta), qos=1, retain=True)

    def publish_status(self, status: dict) -> None:
        self.status = status
        self.c.publish(T_STATUS, json.dumps(status), qos=1, retain=True)

    def publish_fuel(self, history: dict) -> None:
        self.fuel = history
        self.c.publish(T_FUEL, json.dumps(history), qos=1, retain=True)

    def close(self) -> None:
        self.c.publish(T_STATUS, OFFLINE, qos=1, retain=True).wait_for_publish(2)
        self.c.loop_stop()
        self.c.disconnect()


class MqttFeed:
    """Client side: mirrors broker values into a local Bus plus meta/status dicts."""

    def __init__(self, host: str = "localhost", port: int = 1883, client_id: str = "jpcan-client"):
        self.bus = Bus()
        self.meta: dict = {}
        self.status: dict = {}
        self.fuel: dict = {}
        self.connected = False
        self._lock = threading.Lock()
        self.c = _client(f"{client_id}-{int(time.time() * 1000) % 100000}")
        self.c.on_connect = self._on_connect
        self.c.on_disconnect = self._on_disconnect
        self.c.on_message = self._on_message
        self.c.connect_async(host, port, keepalive=30)
        self.c.loop_start()

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        self.connected = True
        client.subscribe(f"{PREFIX}/#", qos=0)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        self.connected = False

    def _on_message(self, client, userdata, msg):
        try:
            if msg.topic.startswith(T_VALUE):
                self.bus.publish(decode_reading(msg.topic[len(T_VALUE):], msg.payload))
            elif msg.topic == T_META:
                self.meta = json.loads(msg.payload)
            elif msg.topic == T_STATUS:
                self.status = json.loads(msg.payload)
            elif msg.topic == T_FUEL:
                self.fuel = json.loads(msg.payload)
        except (ValueError, TypeError):
            pass  # ignore malformed messages

    def trip_reset(self) -> None:
        self.c.publish(T_TRIP_RESET, b"1", qos=1)

    def fillup(self, gallons: float, price: float | None = None) -> None:
        self.c.publish(T_FILLUP, json.dumps({"gallons": gallons, "price": price}), qos=1)

    def close(self) -> None:
        self.c.loop_stop()
        self.c.disconnect()
