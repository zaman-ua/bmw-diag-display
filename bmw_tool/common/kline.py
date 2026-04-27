"""
K-Line transport layer for BMW diagnostics.

Provides:
  - KLine class: serial port wrapper with proper timing
  - KWP2000 extended (B8 header) frame send/receive for DDE/EGS
  - DS2 classic frame send/receive for IKE/LCM/EWS/etc.
  - Wake-up sequence for DDE5

All ECUs on old BMW diesels (E39/E46/E53) talk on one shared K-Line bus:
  9600 baud, 8N1, DTR=false, half-duplex with local echo.
"""
import time
from typing import Optional, List

try:
    import serial
except ImportError:
    serial = None  # allow import without pyserial for testing


# Timing constants (seconds) — based on Deep OBD trace analysis
P1_MAX = 0.020   # inter-byte time in response
P2_MIN = 0.025   # delay between request and response
P3_MIN = 0.055   # delay between two requests
P4_MIN = 0.005   # inter-byte time in request


def cs_xor(data: bytes) -> int:
    """
    Checksum for both KWP2000 BMW ext (B8 header) and DS2 classic.
    
    Verified from init.trc on E53 M57TU:
        B8 12 F1 01 A2 → F8    (wake-up)
        B8 12 F1 02 1A 80 → C3 (IDENT)
        B8 12 F1 06 23 00 00 00 07 40 → 39  (ReadMem)
    
    All of these are XOR, not ADD, despite being "KWP2000".
    """
    r = 0
    for b in data:
        r ^= b
    return r


# ────────────────────────────────────────────────────────
# Frame builders
# ────────────────────────────────────────────────────────

def build_kwp_ext(dst: int, payload: bytes, tester: int = 0xF1) -> bytes:
    """
    KWP2000 BMW extended header frame:
        [B8] [DST] [TESTER] [LEN] [DATA...] [CS_XOR]
    where LEN is length of DATA only.

    IMPORTANT: Checksum is XOR, not ADD — verified from init.trc on E53.
    Example: B8 12 F1 02 1A 80 → checksum byte 0xC3
             = B8 ^ 12 ^ F1 ^ 02 ^ 1A ^ 80 = 0xC3 ✓
    """
    length = len(payload)
    frame = bytes([0xB8, dst, tester, length]) + payload
    return frame + bytes([cs_xor(frame)])


def build_ds2(addr: int, payload: bytes) -> bytes:
    """
    DS2 classic frame:
        [ADDR] [LEN] [DATA...] [CS_XOR]
    where LEN = total frame bytes including ADDR, LEN, DATA and CS.
    """
    length = 3 + len(payload)  # addr(1) + len(1) + data + cs(1)
    frame = bytes([addr, length]) + payload
    return frame + bytes([cs_xor(frame)])


def parse_kwp_ext_response(data: bytes) -> Optional[bytes]:
    """
    Parse a KWP ext response: [B8] [F1] [SRC] [LEN] [DATA...] [CS_XOR]
    Returns DATA or None if malformed.
    Note: on response the tester (F1) comes BEFORE source ECU.
    """
    if len(data) < 6:
        return None
    if data[0] != 0xB8:
        return None
    length = data[3]
    total = 4 + length + 1
    if len(data) < total:
        return None
    if cs_xor(data[:4 + length]) != data[4 + length]:
        return None
    return bytes(data[4:4 + length])


def parse_ds2_response(data: bytes) -> Optional[bytes]:
    """
    Parse a DS2 response: [ADDR] [LEN] [DATA...] [CS]
    Returns DATA or None if malformed.
    """
    if len(data) < 4:
        return None
    length = data[1]
    if len(data) < length:
        return None
    frame = bytes(data[:length])
    if cs_xor(frame[:-1]) != frame[-1]:
        return None
    return frame[2:-1]


# ────────────────────────────────────────────────────────
# K-Line transport
# ────────────────────────────────────────────────────────

class KLine:
    """
    Wraps a pyserial port for K-Line diagnostic traffic.
    Handles local echo removal (half-duplex K-Line loops back every
    byte we send before any response arrives).
    """

    def __init__(self, port: str, baud: int = 9600, debug: bool = False):
        if serial is None:
            raise ImportError("pyserial required: pip install pyserial")
        self.ser = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.05,        # 50 ms inter-byte timeout
            write_timeout=1.0,
            dsrdtr=False,
            rtscts=False,
        )
        # Important: DTR must be false (K-Line idle state)
        self.ser.dtr = False
        self.ser.rts = False
        self.debug = debug
        self._last_tx = 0.0

    def close(self):
        if self.ser:
            self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # Raw byte-level I/O -------------------------------------------------

    def _flush(self):
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

    def _send_raw(self, data: bytes):
        """Send bytes, wait for echo, consume it."""
        # Enforce P3 between requests
        since = time.monotonic() - self._last_tx
        if since < P3_MIN:
            time.sleep(P3_MIN - since)

        self._flush()
        if self.debug:
            print(f"  TX: {data.hex(' ')}")
        self.ser.write(data)
        self.ser.flush()

        # Consume echo (K-Line loopback)
        echo = bytearray()
        deadline = time.monotonic() + 0.5
        while len(echo) < len(data) and time.monotonic() < deadline:
            chunk = self.ser.read(len(data) - len(echo))
            if chunk:
                echo.extend(chunk)
        if bytes(echo) != data and self.debug:
            print(f"  echo mismatch: got {bytes(echo).hex(' ')}")

        self._last_tx = time.monotonic()

    def _read_response(self, timeout: float = 1.0) -> bytes:
        """Read response bytes until gap > P1_MAX or overall timeout."""
        buf = bytearray()
        deadline = time.monotonic() + timeout
        last_rx = None
        while time.monotonic() < deadline:
            chunk = self.ser.read(64)
            if chunk:
                buf.extend(chunk)
                last_rx = time.monotonic()
            elif last_rx and (time.monotonic() - last_rx) > P1_MAX * 3:
                # No bytes for 3*P1 → response complete
                break
            else:
                time.sleep(0.005)
        return bytes(buf)

    # Protocol-aware send/recv -------------------------------------------

    def send_kwp_ext(self, dst: int, payload: bytes,
                     timeout: float = 1.0) -> Optional[bytes]:
        """
        Send a KWP2000 ext frame and return the parsed response payload.
        Returns None on timeout or bad checksum.
        """
        frame = build_kwp_ext(dst, payload)
        self._send_raw(frame)
        resp = self._read_response(timeout)
        if self.debug and resp:
            print(f"  RX: {resp.hex(' ')}")
        return parse_kwp_ext_response(resp)

    def send_ds2(self, addr: int, payload: bytes,
                 timeout: float = 1.0) -> Optional[bytes]:
        """
        Send a DS2 classic frame and return the parsed response payload.
        """
        frame = build_ds2(addr, payload)
        self._send_raw(frame)
        resp = self._read_response(timeout)
        if self.debug and resp:
            print(f"  RX: {resp.hex(' ')}")
        return parse_ds2_response(resp)

    # DDE-specific helpers -----------------------------------------------

    def dde_wakeup(self, dde_addr: int = 0x12) -> bool:
        """
        Wake up a DDE5 ECU. DDE5 sleeps on power-up until it sees an
        initial KWP $A2 StartCommunication. Returns True if any response
        arrived (even negative 7F A2 11 — means the ECU is alive).

        Frame on the wire (verified from init.trc):
            B8 12 F1 01 A2 F8
            │  │  │  │  │  └ XOR checksum (B8^12^F1^01^A2 = F8)
            │  │  │  │  └─── payload: $A2 StartCommunication
            │  │  │  └────── LEN = 1 (payload length)
            │  │  └───────── tester = F1
            │  └──────────── DST = 0x12 (DDE)
            └─────────────── B8 ext header marker

        Expected response: B8 F1 12 03 7F A2 11 94
            ↑ 7F=negative, A2=echo service, 11=service not supported yet
        """
        resp = self.send_kwp_ext(dde_addr, bytes([0xA2]), timeout=0.5)
        # Negative response is EXPECTED here — DDE is now alive.
        # Real confirmation is any reply at all.
        return resp is not None

    def dde_ident(self, dde_addr: int = 0x12) -> Optional[bytes]:
        """
        Issue KWP2000 IDENT request ($1A 80) to a DDE.
        Returns the ID payload (BMW PN + HW/SW + date + etc.) or None.
        """
        return self.send_kwp_ext(dde_addr, bytes([0x1A, 0x80]), timeout=1.0)

    def dde_read_memory(self, addr: int, length: int,
                        dde_addr: int = 0x12) -> Optional[bytes]:
        """
        KWP2000 ReadMemoryByAddress ($23):
            [23] [AH] [AM] [AL] [LH] [LL]
        Used to read the AIF block (VIN/date/etc.) at addr 0x000000.
        """
        req = bytes([
            0x23,
            (addr >> 16) & 0xFF,
            (addr >> 8) & 0xFF,
            addr & 0xFF,
            (length >> 8) & 0xFF,
            length & 0xFF,
        ])
        return self.send_kwp_ext(dde_addr, req, timeout=1.5)

    def dde_read_param(self, dde_mem_addr: int, size: int,
                       dde_addr: int = 0x12) -> Optional[bytes]:
        """
        Read a single BetriebswTab parameter using KWP2000 $2C $10:
            Request:  [2C] [10] [AH] [AL]
            Response: [6C] [10] [DATA...]
        
        The response does NOT echo the address — positive response is just
        subfunction echo + data bytes.
        
        Verified from ifh.trc on E53 M57TU (DDE5):
            Req: B8 12 F1 04 2C 10 00 6E 0D
            Rsp: B8 F1 12 04 6C 10 1F 87 BB
                 └─ header ─┘  └─ 6C 10 ─┘ └ data ┘ └CS┘
                             parsed payload = [6C 10 1F 87]
                             data = [1F 87] (offset 2, size=2)
        
        Returns raw bytes of size `size`, or None on error.
        """
        req = bytes([
            0x2C, 0x10,
            (dde_mem_addr >> 8) & 0xFF,
            dde_mem_addr & 0xFF,
        ])
        resp = self.send_kwp_ext(dde_addr, req, timeout=0.5)
        if resp is None:
            return None
        # Response payload layout: [6C] [10] [DATA...]
        # Skip subfunction echo (2 bytes) to get the data
        if len(resp) < 2 + size:
            return None
        if resp[0] != 0x6C:  # positive response to $2C
            return None
        return resp[2:2 + size]

    def dde_read_params_batch(self, addrs: list, size: int = 2,
                              dde_addr: int = 0x12) -> Optional[list]:
        """
        Read MULTIPLE parameters in ONE KWP request.
        
        This is the technique used by the gauge.s-sorek.uk project:
        send $2C $10 followed by N×2-byte addresses, and get all N values
        back in one response. ~10x faster than reading one at a time.
        
        Args:
            addrs: list of 16-bit DDE memory addresses
            size:  bytes per parameter (typically 2)
        
        Request frame:
            [B8][12][F1][LEN][2C][10][AH1][AL1][AH2][AL2]...[CS]
            where LEN = 2 + N*2
        
        Response frame:
            [B8][F1][12][LEN][6C][10][D1H][D1L][D2H][D2L]...[CS]
            where LEN = 2 + N*size
        
        Verified from gauge.s-sorek.uk DDE5-M57TU.json:
            10 params in one request, LEN=0x16, CS=0x02 (XOR) ✓
        
        Returns list of raw bytes tuples, or None on failure.
        """
        # Build payload: [2C][10] + N × [AH][AL]
        payload = bytearray([0x2C, 0x10])
        for addr in addrs:
            payload.append((addr >> 8) & 0xFF)
            payload.append(addr & 0xFF)
        
        resp = self.send_kwp_ext(dde_addr, bytes(payload), timeout=1.0)
        if resp is None:
            return None
        
        # Response layout: [6C][10][data for param1][data for param2]...
        if len(resp) < 2 + len(addrs) * size:
            return None
        if resp[0] != 0x6C:
            return None
        
        # Extract each parameter's raw bytes
        result = []
        offset = 2  # skip [6C][10]
        for _ in addrs:
            result.append(bytes(resp[offset:offset + size]))
            offset += size
        
        return result
