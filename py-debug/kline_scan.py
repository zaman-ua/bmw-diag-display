#!/usr/bin/env python3
"""
BMW K+DCAN Cable Full Auto-Scan Test v3.0
==========================================
Reproduces EXACT Deep OBD auto-detection sequence from traces.
Tests ALL protocols for D_MOTOR (DDE) with correct port settings.

From Deep OBD traces:
  D_MOTOR tries 4 protocols in order:
  1. BMW-FAST  (0x010F) @ 115200,8N1 → DTR=true  (D-CAN mode)
  2. KWP2000*  (0x010D) @ 9600,8E1  → DTR=false (K-Line mode)
  3. D-CAN     (0x0110) @ 500000,8N1 → DTR=true  (D-CAN mode)
  4. DS2       (0x0006) @ 9600,8N1  → DTR=false (K-Line mode)

Also tests DS2 to body ECUs (IKE 0x44, DDE 0x12, DME 0x13).

Usage:
  sudo python3 kline_scan.py /dev/ttyUSB0
"""
import serial, time, sys

port = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'
TIMEOUT = 2.0

def cs_add(data):
    """BMW-FAST/KWP2000 checksum: sum of bytes & 0xFF"""
    return sum(data) & 0xFF

def cs_xor(data):
    """DS2 checksum: XOR of bytes"""
    r = 0
    for b in data: r ^= b
    return r

def open_port(baud, parity, dtr_state):
    """Open serial port with exact settings from Deep OBD traces."""
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.bytesize = serial.EIGHTBITS
    ser.parity = parity
    ser.stopbits = serial.STOPBITS_ONE
    ser.timeout = TIMEOUT
    ser.write_timeout = 1.0
    ser.dtr = dtr_state
    ser.rts = False
    ser.open()
    ser.dtr = dtr_state  # force after open
    ser.rts = False
    time.sleep(0.1)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    return ser

def send_recv(ser, frame, label, expect_echo=True):
    """Send frame, optionally read echo, read response."""
    print(f"  TX: {frame.hex(' ')}")
    ser.reset_input_buffer()
    ser.write(frame)
    ser.flush()

    # Read echo
    if expect_echo:
        t0 = time.time()
        echo = b''
        while len(echo) < len(frame) and time.time() - t0 < 0.5:
            d = ser.read(len(frame) - len(echo))
            if d: echo += d
        if echo:
            ok = "✓" if echo == frame else "✗"
            print(f"  Echo: {echo.hex(' ')}  {ok}")
        else:
            print(f"  Echo: NONE")

    # Read response
    t0 = time.time()
    resp = b''
    while time.time() - t0 < TIMEOUT:
        d = ser.read(1)
        if d:
            resp += d
            # Keep reading with inter-byte timeout
            while True:
                d2 = ser.read(1)
                if d2: resp += d2
                else: break
            break

    if resp:
        print(f"  RX: {resp.hex(' ')}")
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in resp)
        print(f"  ASCII: {asc}")
        return resp
    else:
        print(f"  RX: NO RESPONSE")
        return None

def test_bmwfast(ecu_addr, label):
    """
    BMW-FAST protocol (concept 0x010F)
    CommParameter: 0000010F 0001C200 000004B0 00000014 0000000A 00000002 00001388
    Baud: 115200, Parity: NONE, DTR: true (D-CAN mode on cable)
    Frame: standard BMW-FAST with ADD checksum
    """
    print(f"\n{'='*60}")
    print(f"BMW-FAST (0x010F) @ 115200 8N1 DTR=true → {label} (0x{ecu_addr:02X})")
    print(f"{'='*60}")

    ser = open_port(115200, serial.PARITY_NONE, True)

    # IDENT: $1A $80 ReadECUIdentification
    data = bytes([0x82, ecu_addr, 0xF1, 0x1A, 0x80])
    frame = data + bytes([cs_add(data)])
    print(f"\n  --- IDENT ($1A $80) ---")
    r = send_recv(ser, frame, "IDENT")

    ser.close()
    time.sleep(0.2)
    return r

def test_kwp2000s(ecu_addr, label):
    """
    KWP2000* protocol (concept 0x010D)
    CommParameter: 0000010D 00002580 000001F4 00000019 00000014 00000000 00000002 00001388
    Baud: 9600, Parity: EVEN (8E1), DTR: false (K-Line mode)
    Frame: EXTENDED format (B8 header) with ADD checksum

    NOTE: In traces, KWP2000* uses B8 header (extended format):
      B8 [DST] [F1] [LEN] [DATA...] [CS_ADD]
    """
    print(f"\n{'='*60}")
    print(f"KWP2000* (0x010D) @ 9600 8E1 DTR=false → {label} (0x{ecu_addr:02X})")
    print(f"{'='*60}")

    ser = open_port(9600, serial.PARITY_EVEN, False)

    # IDENT: $1A $80 - Extended format from trace
    # Trace shows: B8 12 F1 02 1A 80 C3
    # B8 = extended header (length in byte[3])
    # 12 = ECU addr, F1 = tester, 02 = data length
    # 1A 80 = ReadECUIdentification
    # C3 = ADD checksum
    data = bytes([0xB8, ecu_addr, 0xF1, 0x02, 0x1A, 0x80])
    cs = cs_add(data)
    frame = data + bytes([cs])
    print(f"\n  --- IDENT ($1A $80) extended format ---")
    print(f"  Checksum verify: 0x{cs:02X} (B8+{ecu_addr:02X}+F1+02+1A+80 = 0x{sum(data):X} & FF = 0x{cs:02X})")
    r = send_recv(ser, frame, "IDENT")

    ser.close()
    time.sleep(0.2)
    return r

def test_kwp2000s_standard_hdr(ecu_addr, label):
    """
    Same as KWP2000* but with STANDARD header format (82 instead of B8).
    Some ECUs might respond to standard format even on 0x010D.
    """
    print(f"\n{'='*60}")
    print(f"KWP2000* (std hdr) @ 9600 8E1 DTR=false → {label} (0x{ecu_addr:02X})")
    print(f"{'='*60}")

    ser = open_port(9600, serial.PARITY_EVEN, False)

    # Standard header: 82 [DST] [F1] [1A] [80] [CS]
    data = bytes([0x82, ecu_addr, 0xF1, 0x1A, 0x80])
    frame = data + bytes([cs_add(data)])
    print(f"\n  --- IDENT ($1A $80) standard format ---")
    r = send_recv(ser, frame, "IDENT")

    ser.close()
    time.sleep(0.2)
    return r

def test_kwp2000_8n1(ecu_addr, label):
    """
    Try KWP2000 with 8N1 (no parity) - some cables/ECUs need this.
    Both standard and extended headers.
    """
    print(f"\n{'='*60}")
    print(f"KWP2000 @ 9600 8N1 DTR=false → {label} (0x{ecu_addr:02X})")
    print(f"{'='*60}")

    ser = open_port(9600, serial.PARITY_NONE, False)

    # Extended header
    data = bytes([0xB8, ecu_addr, 0xF1, 0x02, 0x1A, 0x80])
    frame = data + bytes([cs_add(data)])
    print(f"\n  --- IDENT extended B8 header ---")
    r = send_recv(ser, frame, "IDENT ext")

    if not r:
        time.sleep(0.1)
        # Standard header
        data = bytes([0x82, ecu_addr, 0xF1, 0x1A, 0x80])
        frame = data + bytes([cs_add(data)])
        print(f"\n  --- IDENT standard 82 header ---")
        r = send_recv(ser, frame, "IDENT std")

    ser.close()
    time.sleep(0.2)
    return r

def test_dcan(ecu_addr, label):
    """
    D-CAN protocol (concept 0x0110)
    CommParameter: 00000110 0007A120 ...
    Baud: 500000, Parity: NONE, DTR: true (D-CAN mode)
    """
    print(f"\n{'='*60}")
    print(f"D-CAN (0x0110) @ 500000 8N1 DTR=true → {label} (0x{ecu_addr:02X})")
    print(f"{'='*60}")

    try:
        ser = open_port(500000, serial.PARITY_NONE, True)
    except Exception as e:
        print(f"  Cannot open at 500000 baud: {e}")
        return None

    # Same frame format as BMW-FAST
    data = bytes([0x82, ecu_addr, 0xF1, 0x1A, 0x80])
    frame = data + bytes([cs_add(data)])
    print(f"\n  --- IDENT ($1A $80) ---")
    r = send_recv(ser, frame, "IDENT")

    ser.close()
    time.sleep(0.2)
    return r

def test_ds2(ecu_addr, label):
    """
    DS2 protocol (concept 0x0006)
    CommParameter: 00000006 00002580 [ecu_addr] ...
    Baud: 9600, Parity: NONE, DTR: false (K-Line mode)
    Frame: [ADDR] [LEN] [DATA...] [XOR_CS]
    IDENT = [ADDR] [04] [00] [XOR_CS]
    """
    print(f"\n{'='*60}")
    print(f"DS2 (0x0006) @ 9600 8N1 DTR=false → {label} (0x{ecu_addr:02X})")
    print(f"{'='*60}")

    ser = open_port(9600, serial.PARITY_NONE, False)

    # DS2 IDENT: [addr] [04] [00] [xor]
    data = bytes([ecu_addr, 0x04, 0x00])
    frame = data + bytes([cs_xor(data)])
    print(f"\n  --- DS2 IDENT ---")
    r = send_recv(ser, frame, "DS2 IDENT")

    ser.close()
    time.sleep(0.2)
    return r

def test_dcan_uds(ecu_addr, label):
    """
    D-CAN with UDS ($22 F150) - used by G_ZGW, G_CAS, G_FRM
    Baud: 500000, DTR: true
    """
    print(f"\n{'='*60}")
    print(f"D-CAN UDS ($22 F150) @ 500000 8N1 DTR=true → {label} (0x{ecu_addr:02X})")
    print(f"{'='*60}")

    try:
        ser = open_port(500000, serial.PARITY_NONE, True)
    except Exception as e:
        print(f"  Cannot open at 500000 baud: {e}")
        return None

    # UDS ReadDataByIdentifier $22 $F1 $50
    data = bytes([0x83, ecu_addr, 0xF1, 0x22, 0xF1, 0x50])
    frame = data + bytes([cs_add(data)])
    print(f"\n  --- UDS $22 F150 ---")
    r = send_recv(ser, frame, "UDS IDENT")

    ser.close()
    time.sleep(0.2)
    return r


# ═══════════════════════════════════════════════════════════
# MAIN - reproduce exact Deep OBD auto-detection sequence
# ═══════════════════════════════════════════════════════════

print(f"""
╔══════════════════════════════════════════════════════════╗
║  BMW K+DCAN Full Auto-Scan v3.0                         ║
║  Port: {port:50s}║
║  Reproducing exact Deep OBD detection sequence           ║
╚══════════════════════════════════════════════════════════╝
""")

results = []

# ── Phase 1: D-CAN UDS (F-series gateway detection) ──
print("\n" + "█" * 60)
print("█  PHASE 1: D-CAN UDS (G_ZGW, G_CAS, G_FRM)")
print("█" * 60)
for addr, name in [(0x10, "G_ZGW"), (0x40, "G_CAS"), (0x72, "G_FRM")]:
    r = test_dcan_uds(addr, name)
    if r: results.append(("D-CAN UDS", name, r))

# ── Phase 2: D_CAS (E-series CAS via BMW-FAST then KWP2000*) ──
print("\n" + "█" * 60)
print("█  PHASE 2: D_CAS (BMW-FAST → KWP2000*)")
print("█" * 60)
r = test_bmwfast(0x40, "D_CAS")
if r: results.append(("BMW-FAST", "D_CAS", r))
r = test_kwp2000s(0x40, "D_CAS")
if r: results.append(("KWP2000*", "D_CAS", r))

# ── Phase 3: D_MOTOR / DDE (the main target!) ──
print("\n" + "█" * 60)
print("█  PHASE 3: D_MOTOR / DDE (ECU 0x12) - ALL PROTOCOLS")
print("█" * 60)

# 3a. BMW-FAST @ 115200
r = test_bmwfast(0x12, "D_MOTOR")
if r: results.append(("BMW-FAST", "D_MOTOR", r))

# 3b. KWP2000* @ 9600 8E1 (extended B8 header)
r = test_kwp2000s(0x12, "D_MOTOR")
if r: results.append(("KWP2000*", "D_MOTOR", r))

# 3c. D-CAN @ 500000
r = test_dcan(0x12, "D_MOTOR")
if r: results.append(("D-CAN", "D_MOTOR", r))

# 3d. KWP2000 @ 9600 8N1 (both header formats)
r = test_kwp2000_8n1(0x12, "D_MOTOR")
if r: results.append(("KWP2000-8N1", "D_MOTOR", r))

# 3e. KWP2000* standard header @ 9600 8E1
r = test_kwp2000s_standard_hdr(0x12, "D_MOTOR")
if r: results.append(("KWP2000*-std", "D_MOTOR", r))

# ── Phase 4: DS2 body modules ──
print("\n" + "█" * 60)
print("█  PHASE 4: DS2 protocol (body ECUs)")
print("█" * 60)
for addr, name in [(0x44, "IKE"), (0x12, "DDE/DS2"), (0x13, "EGS"), (0x00, "ZGM")]:
    r = test_ds2(addr, name)
    if r: results.append(("DS2", name, r))

# ── Phase 5: Additional D_MOTOR protocols ──
print("\n" + "█" * 60)
print("█  PHASE 5: D_LM / D_ZGM (BMW-FAST → KWP2000*)")
print("█" * 60)
for addr, name in [(0x70, "D_LM"), (0x00, "D_ZGM")]:
    r = test_bmwfast(addr, name)
    if r: results.append(("BMW-FAST", name, r))
    r = test_kwp2000s(addr, name)
    if r: results.append(("KWP2000*", name, r))

# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════
print("\n" + "═" * 60)
print("RESULTS SUMMARY")
print("═" * 60)

if results:
    print(f"\n✓ GOT {len(results)} RESPONSE(S):\n")
    for proto, name, data in results:
        print(f"  {proto:15s} {name:10s} → {data[:20].hex(' ')}...")
else:
    print("""
✗ NO RESPONSES from any protocol.

Possible causes:
  1. Cable not connected to car
  2. Ignition OFF (must be ON or ACC)
  3. K-Line wire broken (pin 7/8 on OBD-II)
  4. Cable hardware issue
  
If connected to car with ignition ON:
  - Try switching cable to other position (if has switch)
  - Check OBD-II connector pins 7, 8, 16 (power), 4/5 (ground)
""")

print("\nDone!")