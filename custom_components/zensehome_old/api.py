from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional, List, Dict

@dataclass(frozen=True)
class ZenseDevice:
    did: int
    name: str

class ZenseApi:
    def __init__(self, host: str, port: int, code: int, timeout: float = 12.0):
        self._host = host
        self._port = port
        self._code = code
        self._timeout = timeout
        self._lock = asyncio.Lock()

    async def _read_until_terminator(self, reader: asyncio.StreamReader) -> str:
        buf = ""
        while True:
            chunk = await asyncio.wait_for(reader.read(1024), timeout=self._timeout)
            if not chunk:
                break
            buf += chunk.decode(errors="replace")
            if "<<" in buf:
                break
        return buf

    async def _call(self, cmd: str) -> str:
        async with self._lock:
            reader: asyncio.StreamReader
            writer: asyncio.StreamWriter
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=self._timeout,
            )
            try:
                writer.write(f">>Login {self._code}<<".encode())
                await writer.drain()
                _ = await self._read_until_terminator(reader)

                writer.write(cmd.encode())
                await writer.drain()
                resp = await self._read_until_terminator(reader)

                try:
                    writer.write(b">>Logout<<")
                    await writer.drain()
                    _ = await self._read_until_terminator(reader)
                except Exception:
                    pass

                return resp
            finally:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

    async def get_devices(self) -> List[int]:
        resp = await self._call(">>Get Devices<<")
        if ">>Get Devices " in resp:
            part = resp.split(">>Get Devices ")[1].split("<<")[0]
            ids = [x.strip() for x in part.split(",")]
            return [int(x) for x in ids if x.isdigit()]
        return []

    async def get_name(self, did: int) -> str:
        resp = await self._call(f">>Get Name {did}<<")
        if ">>Get Name " in resp:
            nm = resp.split(">>Get Name ")[1].split("<<")[0].strip().strip("'")
            if nm and nm.lower() != "timeout":
                return nm
        return f"Device_{did}"

    async def get_level(self, did: int) -> Optional[int]:
        resp = await self._call(f">>Get {did}<<")
        if ">>Get " in resp:
            try:
                val = resp.split(">>Get ")[1].split("<<")[0].strip()
                return int(val)
            except Exception:
                return None
        return None

    async def set_off(self, did: int) -> None:
        await self._call(f">>Set {did} 0<<")

    async def set_on(self, did: int, scale: int = 100) -> None:
        await self._call(f">>Set {did} {scale}<<")

    async def fade(self, did: int, level: int, scale: int = 100) -> None:
        level = max(0, min(scale, int(level)))
        await self._call(f">>Fade {did} {level}<<")

    async def discover(self) -> List[ZenseDevice]:
        dids = await self.get_devices()
        devices: List[ZenseDevice] = []
        for did in dids:
            name = await self.get_name(did)
            devices.append(ZenseDevice(did=did, name=name))
        return devices

def guess_entity_type(name: str) -> str:
    n = (name or "").strip().lower()
    keywords_switch = ("stik", "stikk", "kontakt", "ventilation", "pumpe", "relay", "relæ")
    for kw in keywords_switch:
        if kw in n:
            return "switch"
    return "light"
