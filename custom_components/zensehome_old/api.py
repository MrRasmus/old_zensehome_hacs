from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from homeassistant.core import HomeAssistant

from .const import BRIGHTNESS_SCALE, DEFAULT_CMD_GAP_S


class ZenseClient:
    def __init__(self, host: str, port: int, code: int) -> None:
        self.host = host
        self.port = int(port)
        self.code = int(code)

        self.logger = logging.getLogger(__name__)

        self._lock = asyncio.Lock()

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._logged_in = False

        self._last_tx = 0.0
        self._cmd_gap_s = float(DEFAULT_CMD_GAP_S)

        self._bucket_capacity = 3.0
        self._bucket_tokens = self._bucket_capacity
        self._bucket_refill_per_sec = 2.5
        self._bucket_last = time.monotonic()

        self._timeout_s = 12.0

    async def _close(self) -> None:
        try:
            if self._writer is not None:
                self._writer.close()
                try:
                    await self._writer.wait_closed()
                except Exception:
                    pass
        except Exception:
            pass
        self._reader = None
        self._writer = None
        self._logged_in = False

    async def _connect(self) -> None:
        await self._close()
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port),
            timeout=self._timeout_s,
        )
        self._logged_in = False

    async def _bucket_wait(self) -> None:
        now = time.monotonic()
        dt = now - self._bucket_last
        self._bucket_last = now
        self._bucket_tokens = min(
            self._bucket_capacity,
            self._bucket_tokens + dt * self._bucket_refill_per_sec,
        )
        if self._bucket_tokens < 1.0:
            need = 1.0 - self._bucket_tokens
            wait = need / self._bucket_refill_per_sec
            await asyncio.sleep(max(0.0, wait))
            now2 = time.monotonic()
            dt2 = now2 - self._bucket_last
            self._bucket_last = now2
            self._bucket_tokens = min(
                self._bucket_capacity,
                self._bucket_tokens + dt2 * self._bucket_refill_per_sec,
            )
        self._bucket_tokens -= 1.0

    async def _rate_limit(self) -> None:
        await self._bucket_wait()
        now = time.monotonic()
        wait = self._cmd_gap_s - (now - self._last_tx)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_tx = time.monotonic()

    async def _recv_frame(self) -> str:
        if self._reader is None:
            return ""
        buf = ""
        end_time = time.monotonic() + self._timeout_s
        while time.monotonic() < end_time:
            chunk = await asyncio.wait_for(self._reader.read(1024), timeout=self._timeout_s)
            if not chunk:
                break
            buf += chunk.decode(errors="replace")
            if "<<" in buf:
                idx = buf.find("<<")
                return buf[: idx + 2]
        return buf

    async def _send_raw(self, cmd: str) -> str:
        if self._writer is None:
            return ""
        await self._rate_limit()
        self._writer.write(cmd.encode())
        await asyncio.wait_for(self._writer.drain(), timeout=self._timeout_s)
        return await self._recv_frame()

    async def _login(self) -> bool:
        if self._reader is None or self._writer is None:
            await self._connect()
        resp = await self._send_raw(f">>Login {self.code}<<")
        if ">>Login Ok<<" in resp:
            self._logged_in = True
            await asyncio.sleep(0.2)
            return True
        await self._close()
        return False

    async def send_command(self, cmd: str, retry: int = 2) -> str:
        async with self._lock:
            backoff = 0.25
            for attempt in range(retry + 1):
                try:
                    if self._reader is None or self._writer is None or not self._logged_in:
                        ok = await self._login()
                        if not ok:
                            if attempt < retry:
                                await asyncio.sleep(backoff)
                                backoff = min(2.0, backoff * 1.7)
                                continue
                            return ""

                    resp = await self._send_raw(cmd)
                    if not resp or "Timeout" in resp:
                        raise TimeoutError

                    return resp
                except Exception:
                    await self._close()
                    if attempt < retry:
                        await asyncio.sleep(backoff)
                        backoff = min(2.0, backoff * 1.7)
                        continue
                    return ""
        return ""

    async def get_devices(self) -> list[int]:
        resp = await self.send_command(">>Get Devices<<")
        if ">>Get Devices " in resp:
            part = resp.split(">>Get Devices ", 1)[1].split("<<", 1)[0]
            out: list[int] = []
            for x in part.split(","):
                x = x.strip()
                if x.isdigit():
                    out.append(int(x))
            return out
        return []

    async def get_name(self, did: int) -> str:
        resp = await self.send_command(f">>Get Name {did}<<")
        if ">>Get Name " in resp:
            return resp.split(">>Get Name ", 1)[1].split("<<", 1)[0].strip().strip("'")
        return f"Device_{did}"

    async def get_level(self, did: int) -> Optional[int]:
        resp = await self.send_command(f">>Get {did}<<")
        if ">>Get " in resp:
            try:
                return int(resp.split(">>Get ", 1)[1].split("<<", 1)[0].strip())
            except Exception:
                return None
        return None

    async def set_on(self, did: int) -> bool:
        return bool(await self.send_command(f">>Set {did} {BRIGHTNESS_SCALE}<<"))

    async def set_off(self, did: int) -> bool:
        return bool(await self.send_command(f">>Set {did} 0<<"))

    async def fade(self, did: int, level: int) -> bool:
        level = max(0, min(BRIGHTNESS_SCALE, int(level)))
        return bool(await self.send_command(f">>Fade {did} {level}<<"))

    async def async_test_connection(self, hass: HomeAssistant) -> bool:
        try:
            ok = await self._login()
            if not ok:
                return False
            ids = await self.get_devices()
            return True if ids is not None else False
        finally:
            await self._close()

    async def async_get_devices_and_names(self, hass: HomeAssistant) -> dict[int, str]:
        ids = await self.get_devices()
        out: dict[int, str] = {}
        for did in ids:
            out[did] = await self.get_name(did)
        return out

    async def async_get_levels(self, hass: HomeAssistant, ids: list[int]) -> dict[int, Optional[int]]:
        out: dict[int, Optional[int]] = {}
        for did in ids:
            out[did] = await self.get_level(did)
        return out
