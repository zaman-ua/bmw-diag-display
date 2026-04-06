#!/usr/bin/env python3
"""
Minimal K-Line test for BMW DDE5.
Sends raw bytes exactly as EdiabasLib does.

Usage:
  sudo python3 kline_test.py /dev/ttyUSB0
"""
import serial, time, sys

port = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'

# EdiabasLib desktop init sequence:
#   BaudRate = 9600
#   DataBits = 8
#   Parity = None
#   StopBits = One
#   Handshake = None
#   DtrEnable = false
#   RtsEnable = false
#   EcuConnected = true (no fast init!)

print(f"Opening {port} @ 9600 8N1...")
ser = serial.Serial()
ser.port = port
ser.baudrate = 9600
ser.bytesize = serial.EIGHTBITS
ser.parity = serial.PARITY_NONE
ser.stopbits = serial.STOPBITS_ONE
ser.timeout = 2.0
ser.write_timeout = 1.0
# CRITICAL: set DTR before opening to ensure K-Line mode
ser.dtr = False
ser.rts = False
ser.open()

# Force DTR/RTS after open (pyserial may reset them)
ser.dtr = False
ser.rts = False
time.sleep(0.1)

ser.reset_input_buffer()
ser.reset_output_buffer()

print(f"  DTR={ser.dtr} RTS={ser.rts}")
print()

def add_checksum(data):
    """BMW Fast checksum = sum of all bytes & 0xFF"""
    return data + bytes([sum(data) & 0xFF])

def send_and_receive(label, frame_without_cs, timeout=2.0):
    """Send frame, read echo + response."""
    frame = add_checksum(frame_without_cs)
    
    print(f"--- {label} ---")
    print(f"  TX: {frame.hex(' ')}")
    
    ser.reset_input_buffer()
    ser.write(frame)
    ser.flush()
    
    # Read echo (K-Line single-wire: we hear our own TX)
    t0 = time.time()
    echo = b''
    while len(echo) < len(frame) and time.time() - t0 < 0.5:
        d = ser.read(len(frame) - len(echo))
        if d:
            echo += d
    
    if echo:
        match = "✓" if echo == frame else "✗ MISMATCH"
        print(f"  Echo: {echo.hex(' ')}  {match}")
    else:
        print(f"  Echo: NONE (cable may not be in K-Line mode?)")
    
    # Read response
    t0 = time.time()
    resp = b''
    while time.time() - t0 < timeout:
        d = ser.read(1)
        if d:
            resp += d
            # Keep reading while data arrives (100ms inter-byte timeout)
            while True:
                d2 = ser.read(1) 
                if d2:
                    resp += d2
                else:
                    break
            break
    
    if resp:
        print(f"  RX: {resp.hex(' ')}")
        # Try to decode ASCII
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in resp)
        print(f"  ASCII: {asc}")
    else:
        print(f"  RX: NO RESPONSE")
    
    print()
    return resp

# =========================================================
# Test 1: StartDiagnosticSession $10 $81
# Frame: [82] [12] [F1] [10] [81] [cs]
#   82 = format byte: 0x80 | 2 data bytes
#   12 = ECU address (DDE)
#   F1 = tester address
#   10 = service StartDiagnosticSession
#   81 = mode (development session)
# =========================================================
print("=" * 50)
print("Test 1: StartDiagnosticSession")
send_and_receive("StartSession 0x81", bytes([0x82, 0x12, 0xF1, 0x10, 0x81]))

time.sleep(0.5)

# =========================================================
# Test 2: ReadECUIdentification $1A $80
# Frame: [82] [12] [F1] [1A] [80] [cs]
# =========================================================
print("=" * 50)
print("Test 2: ReadECUIdentification")
send_and_receive("IDENT", bytes([0x82, 0x12, 0xF1, 0x1A, 0x80]))

time.sleep(0.5)

# =========================================================
# Test 3: TesterPresent $3E
# Frame: [81] [12] [F1] [3E] [cs]
# =========================================================
print("=" * 50)
print("Test 3: TesterPresent")
send_and_receive("TesterPresent", bytes([0x81, 0x12, 0xF1, 0x3E]))

time.sleep(0.5)

# =========================================================
# Test 4: Try different session modes
# =========================================================
for mode in [0x01, 0x89, 0x85]:
    print("=" * 50)
    print(f"Test 4: StartSession mode 0x{mode:02X}")
    r = send_and_receive(f"Session 0x{mode:02X}", bytes([0x82, 0x12, 0xF1, 0x10, mode]))
    time.sleep(0.3)

# =========================================================
# Test 5: Try with DTR=true (some cables need it for TX)
# =========================================================
print("=" * 50)
print("Test 5: Same with DTR=true during TX")
ser.dtr = True
time.sleep(0.05)
send_and_receive("IDENT+DTR", bytes([0x82, 0x12, 0xF1, 0x1A, 0x80]))
ser.dtr = False
time.sleep(0.3)

# =========================================================
# Test 6: Try 10400 baud
# =========================================================
print("=" * 50)
print("Test 6: Switch to 10400 baud")
ser.baudrate = 10400
time.sleep(0.1)
send_and_receive("IDENT@10400", bytes([0x82, 0x12, 0xF1, 0x1A, 0x80]))
ser.baudrate = 9600
time.sleep(0.3)

# =========================================================
# Test 7: DS2 style (different protocol, different ECU addr format)
# DS2: [addr] [length] [data...] [xor_cs]
# IDENT to DDE: [12] [04] [00] [xor]
# =========================================================
print("=" * 50)
print("Test 7: DS2 IDENT (different protocol)")
ds2_frame = bytes([0x12, 0x04, 0x00])
ds2_cs = 0
for b in ds2_frame: ds2_cs ^= b
ds2_full = ds2_frame + bytes([ds2_cs])
print(f"  TX: {ds2_full.hex(' ')}")
ser.reset_input_buffer()
ser.write(ds2_full)
ser.flush()
time.sleep(0.1)
resp = ser.read(100)
if resp:
    echo_part = resp[:len(ds2_full)]
    data_part = resp[len(ds2_full):]
    print(f"  Echo: {echo_part.hex(' ')}")
    if data_part:
        print(f"  RX: {data_part.hex(' ')}")
        print(f"  ASCII: {''.join(chr(b) if 32<=b<127 else '.' for b in data_part)}")
    else:
        print(f"  RX: NO RESPONSE")
else:
    print(f"  Nothing received at all")
print()

ser.close()
print("Done. Share the full output!")
