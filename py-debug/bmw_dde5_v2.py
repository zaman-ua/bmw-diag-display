#!/usr/bin/env python3
"""
BMW DDE5 M57 Diagnostic Tool v2.0 — Batch KWP2000
====================================================
Sends up to 10 parameter addresses in one $2C $10 request.

Protocol (Bosch EDC16 Funktionsbeschreibung):
  Define:  B8 12 F1 LEN 2C 10 [ADR1_H ADR1_L] [ADR2_H ADR2_L] ... CHK
  Read:    83 12 F1 21 10 CHK  
  Answer:  B8 F1 12 LEN 6C 10 [VAL1_H VAL1_L] [VAL2_H VAL2_L] ... CHK

Params from D50M57B1.PRG (BEST1 XOR 0xF7, BetriebswTab).

  sudo python3 bmw_dde5_v2.py -p /dev/ttyUSB0 --turbo
  sudo python3 bmw_dde5_v2.py -p /dev/ttyUSB0 --turbo --log test.csv
  sudo python3 bmw_dde5_v2.py -p /dev/ttyUSB0 --engine
  sudo python3 bmw_dde5_v2.py -p /dev/ttyUSB0 --rail
  sudo python3 bmw_dde5_v2.py -p /dev/ttyUSB0 --rough
  sudo python3 bmw_dde5_v2.py -p /dev/ttyUSB0 --params rpm,boost,rail
  sudo python3 bmw_dde5_v2.py -p /dev/ttyUSB0 --all
  sudo python3 bmw_dde5_v2.py -p /dev/ttyUSB0 --ident
  sudo python3 bmw_dde5_v2.py -p /dev/ttyUSB0 --faults
  sudo python3 bmw_dde5_v2.py --list

Cable: K+DCAN LEFT (K-Line). pip install pyserial
"""
import serial,time,sys,argparse,logging,csv
from datetime import datetime
from dataclasses import dataclass
from typing import Optional,List,Dict

logging.basicConfig(level=logging.INFO,format='%(asctime)s [%(levelname)s] %(message)s')
log=logging.getLogger('dde5')
ECU,TST,REC=0x12,0xF1,0x10

@dataclass
class P:
    nm:str;bid:str;adr:int;fa:float;fb:float;u:str;fmt:str=".1f";desc:str=""

# ═════════ Parameter table (D50M57B1.PRG BetriebswTab) ═════════
PM={
"rpm":      P("RPM",      "Eng_nAvrg",         0x0091,0.125002,    0.0,   "rpm",  ".0f"),
"rpm2":     P("RPM2",     "Eng_nAvrg_Carb",    0x000C,0.250000,    0.0,   "rpm",  ".0f"),
"coolant":  P("CoolT",    "CTSCD_tClntLin",    0x0005,1.000240,  -41.084, "°C",   ".1f"),
"battery":  P("Batt",     "BattCD_u",          0x0093,0.002456,    0.0,   "V",    ".2f"),
"torque":   P("Torque",   "CoEng_trq",         0x14B6,0.114445,-2500.060, "Nm",   ".1f"),
"torque_p": P("Trq%",     "CoEng_rTrq",        0x0004,0.393699,    0.0,   "%",    ".1f"),
"boost":    P("Boost",    "APSCD_pVal",        0x006E,0.125002,    0.0,   "hPa",  ".0f","Факт.наддув"),
"boost_mv": P("BstMV",    "APSCD_uRaw",        0x006F,0.610958,    0.0,   "mV",   ".0f"),
"atm":      P("Atm",      "BPSCD_pOutVal",     0x009E,0.125002,    0.0,   "hPa",  ".0f","Атмосферное"),
"atm_lin":  P("AtmL",     "BPSCD_pLin",        0x000B,10.002401,   0.0,   "hPa",  ".0f"),
"air_act":  P("AirAct",   "AFSCD_mAirPerCyl",  0x0050,0.048829,-1599.971, "mg/H", ".1f","Факт.воздух/цил"),
"air_tgt":  P("AirTgt",   "AirCtl_mDesVal",    0x0088,0.048829,-1599.971, "mg/H", ".1f","Целевой воздух"),
"air_flow": P("MAF",      "AFSCD_dmAirPerTime",0x0052,0.048829,-1599.971, "Kg/h", ".1f"),
"air_rat":  P("AirR%",    "AFSCD_rAir",        0x0051,0.010000,    0.0,   "%",    ".1f"),
"rail":     P("Rail",     "RailCD_pPeak",      0x00C2,0.030518,    0.0,   "bar",  ".0f","Rail факт"),
"rail_tgt": P("RailT",    "Rail_pSetPoint",    0x00C3,0.030518,    0.0,   "bar",  ".0f","Rail цель"),
"fuel_q":   P("FuelQ",    "InjCtl_qCurr",      0x0055,0.003052,  -99.999, "mg/c", ".2f"),
"fuel_s":   P("FuelS",    "InjCtl_qSet",       0x13BC,0.003052,  -99.999, "mg/c", ".2f"),
"fuel_t":   P("FuelT",    "FTScd_tFuel",       0x005B,0.016787,  -50.138, "°C",   ".1f"),
"int_t":    P("IntT",     "IATSCD_tAir",       0x009C,0.016787,  -50.138, "°C",   ".1f"),
"pedal":    P("Pedal",    "APPCD_rFlt",        0x0066,0.003052,    0.0,   "%",    ".1f"),
"pedal_v":  P("PedV",     "APPCD_uRawAPP1",    0x0064,0.000611,    0.0,   "V",    ".3f"),
"c1":       P("Cyl1",     "InjVlv_nCyl1",      0x1429,0.125002,    0.0,   "rpm",  ".0f"),
"c2":       P("Cyl2",     "InjVlv_nCyl2",      0x142A,0.125002,    0.0,   "rpm",  ".0f"),
"c3":       P("Cyl3",     "InjVlv_nCyl3",      0x142B,0.125002,    0.0,   "rpm",  ".0f"),
"c4":       P("Cyl4",     "InjVlv_nCyl4",      0x142C,0.125002,    0.0,   "rpm",  ".0f"),
"c5":       P("Cyl5",     "InjVlv_nCyl5",      0x142D,0.125002,    0.0,   "rpm",  ".0f"),
"c6":       P("Cyl6",     "InjVlv_nCyl6",      0x142E,0.125002,    0.0,   "rpm",  ".0f"),
"speed":    P("Speed",    "PFlt_vVehFlt_mp",   0x13FA,0.003815,    0.0,   "km/h", ".0f"),
"ehrs":     P("EngH",     "VehDa_tiEngOn",     0x009F,99.9001,     0.0,   "s",    ".0f"),
}

PRESETS={
"turbo": (["rpm","boost","atm","air_act","air_tgt","air_flow","pedal","coolant","int_t","battery"],
          "Турбо диагностика: AirActual vs AirTarget + boost"),
"rail":  (["rpm","rail","rail_tgt","fuel_q","fuel_s","fuel_t","pedal","boost","coolant","battery"],
          "Топливная: Rail + впрыск"),
"engine":(["rpm","coolant","battery","boost","atm","rail","air_flow","pedal","torque","speed"],
          "Основные параметры"),
"rough": (["rpm","c1","c2","c3","c4","c5","c6","fuel_q","coolant","rail"],
          "Неравномерность цилиндров"),
"live":  (["rpm","boost","atm","rail","rail_tgt","coolant","battery"],
          "Быстрый мониторинг"),
}

# ═════════ KWP2000 ═════════
# Checksum: ADD (sum of bytes & 0xFF), NOT XOR!
# Source: EdiabasLib/EdInterfaceBase.cs CalcChecksumBmwFast()
def cs_add(d):
    r=0
    for b in d: r=(r+b)&0xFF
    return r

class KWP:
    def __init__(s,port): s.port=port; s._tp=0

    def _txrx(s,pay,to=2.0):
        n=len(pay)
        hdr=bytes([0x80|n,ECU,TST]) if n<=63 else bytes([0x80,ECU,TST,n])
        fr=hdr+pay; fr+=bytes([cs_add(fr)])
        s.port.reset_input_buffer()
        log.debug(f"TX[{len(fr)}]: {fr.hex(' ')}")
        s.port.write(fr); s.port.flush()
        # Read K-Line echo (single-wire bus echoes our TX)
        t0=time.time(); echo=b''
        while len(echo)<len(fr) and time.time()-t0<0.5:
            d=s.port.read(len(fr)-len(echo))
            if d: echo+=d
        if echo: log.debug(f"Echo[{len(echo)}]: {echo.hex(' ')}")
        # Read response header (3 bytes min for BMW-FAST)
        t0=time.time(); buf=b''
        while len(buf)<4 and time.time()-t0<to:
            d=s.port.read(4-len(buf))
            if d: buf+=d
        if len(buf)<4: return None
        if (buf[0]&0xC0)!=0x80:
            log.debug(f"Bad hdr: {buf.hex(' ')}"); return None
        # Calc telegram length (EdiabasLib TelLengthBmwFast)
        dl=buf[0]&0x3F
        if dl==0:
            if len(buf)>3 and buf[3]==0:
                while len(buf)<6 and time.time()-t0<to:
                    d=s.port.read(6-len(buf))
                    if d: buf+=d
                if len(buf)<6: return None
                tl=(buf[4]<<8)+buf[5]+6
            else:
                tl=buf[3]+4 if len(buf)>3 else 4
        else:
            tl=dl+3
        need=tl+1  # +1 for checksum byte
        while len(buf)<need and time.time()-t0<to:
            d=s.port.read(need-len(buf))
            if d: buf+=d
        log.debug(f"RX[{len(buf)}]: {buf.hex(' ')}")
        if len(buf)>=need:
            calc=cs_add(buf[:tl])
            if calc!=buf[tl]:
                log.debug(f"CS fail: calc=0x{calc:02X} got=0x{buf[tl]:02X}")
        return buf

    def start(s):
        for m in [0x81,0x01,0x89]:
            r=s._txrx(bytes([0x10,m]),to=0.5)
            if r and len(r)>3 and r[3]==0x50: log.info(f"Session 0x{m:02X} ✓"); return True
        return False

    def tp(s):
        if time.time()-s._tp>2: s._txrx(bytes([0x3E]),0.5); s._tp=time.time()

    def ident(s): return s._txrx(bytes([0x1A,0x80]))
    def faults(s): return s._txrx(bytes([0x18,0x00,0xFF,0x00]))
    def clear(s): return s._txrx(bytes([0x14,0xFF,0x00]))

    def batch(s,params):
        """$2C $10 [adr...] then $21 $10 → [val...]. Max 10."""
        if len(params)>10: params=params[:10]
        s._txrx(bytes([0x2C,REC,0x04]),0.5); time.sleep(0.01)
        pay=bytearray([0x2C,REC])
        for p in params: pay+=bytes([(p.adr>>8)&0xFF,p.adr&0xFF])
        r=s._txrx(bytes(pay))
        if not r: return None
        if len(r)>3 and r[3]==0x7F: return None
        time.sleep(0.01)
        r=s._txrx(bytes([0x21,REC]))
        if not r: return None
        ds=None
        for i in range(len(r)-1):
            if r[i]==0x61 and r[i+1]==REC: ds=i+2; break
        if ds is None: return None
        vs=[]
        for j,p in enumerate(params):
            o=ds+j*2
            if o+1<len(r)-1: raw=(r[o]<<8)|r[o+1]; vs.append(raw*p.fa+p.fb)
            else: vs.append(None)
        return vs

# ═════════ Display ═════════
def hdr(ps,tb=False):
    h=f"{'sec':>6s} "
    for p in ps: w=max(len(p.nm),7); h+=f"{p.nm:>{w}s} "
    if tb: h+="  ΔAir  RelBst"
    print(h); print("─"*len(h))

def row(ps,vs,t0,tb=False):
    s=f"{time.time()-t0:6.1f} "; vd={}
    for p,v in zip(ps,vs):
        w=max(len(p.nm),7)
        if v is not None: s+=f"{v:{w}{p.fmt}} "; vd[p.bid]=v
        else: s+=f"{'---':>{w}s} "
    if tb:
        aa=vd.get("AFSCD_mAirPerCyl"); at_=vd.get("AirCtl_mDesVal")
        bp=vd.get("APSCD_pVal"); ap=vd.get("BPSCD_pOutVal")
        if aa is not None and at_ is not None:
            d=aa-at_; m="✓" if abs(d)<50 else "⚠" if abs(d)<100 else "✗"
            s+=f" {d:+5.0f}{m}"
        else: s+="   ---"
        if bp is not None and ap is not None: s+=f" {bp-ap:6.0f}"
        else: s+="    ---"
    print(f"\r{s}",end='',flush=True)
    return vd

# ═════════ Commands ═════════
def c_ident(k):
    print("\n=== ECU Identification ===")
    r=k.ident()
    if r: print(f"  {r[3:-1].hex(' ')}"); print(f"  {''.join(chr(b) if 32<=b<127 else '.' for b in r[3:-1])}")
    else: print("  No response")

def c_faults(k):
    print("\n=== Fault Codes ===")
    r=k.faults()
    if not r: print("  No response"); return
    d=r[4:-1]
    if len(d)<=1: print("  No faults ✓"); return
    for i in range(0,len(d)-2,3): print(f"  DTC 0x{(d[i]<<8)|d[i+1]:04X} st=0x{d[i+2]:02X}")

def c_once(k,keys):
    ps=[PM[x] for x in keys if x in PM]
    for i in range(0,len(ps),10):
        b=ps[i:i+10]; vs=k.batch(b)
        if vs:
            for p,v in zip(b,vs):
                print(f"  {p.nm:15s} {v:{p.fmt}} {p.u}" if v is not None else f"  {p.nm:15s} ---")
        else: print("  batch failed")

def c_live(k,keys,logf=None,tb=False):
    ps=[PM[x] for x in keys if x in PM][:10]
    print(f"\n=== Live [{len(ps)}p] Ctrl+C ===")
    if tb: print("  ΔAir=AirAct−AirTgt: ✓<50 ⚠50-100 ✗>100 mg/Hub\n")
    cw=cf=None
    if logf:
        cf=open(logf,'w',newline=''); cw=csv.writer(cf)
        h=['time','sec']+[p.bid for p in ps]
        if tb: h+=['delta_air','rel_boost']
        cw.writerow(h); print(f"  Log: {logf}")
    hdr(ps,tb); t0=time.time(); n=0
    try:
        while True:
            vs=k.batch(ps)
            if vs:
                vd=row(ps,vs,t0,tb); n+=1
                if cw:
                    r=[datetime.now().isoformat(),f"{time.time()-t0:.2f}"]
                    r+=[f"{v:{p.fmt}}" if v is not None else '' for p,v in zip(ps,vs)]
                    if tb:
                        aa=vd.get("AFSCD_mAirPerCyl"); at_=vd.get("AirCtl_mDesVal")
                        bp=vd.get("APSCD_pVal"); ap=vd.get("BPSCD_pOutVal")
                        r.append(f"{aa-at_:.0f}" if aa is not None and at_ is not None else '')
                        r.append(f"{bp-ap:.0f}" if bp is not None and ap is not None else '')
                    cw.writerow(r)
                if n%20==0: print(); hdr(ps,tb)
            else: print("\r  retry...",end='',flush=True); time.sleep(0.5)
            k.tp(); time.sleep(0.05)
    except KeyboardInterrupt:
        el=time.time()-t0; print(f"\n\n  {n} samples / {el:.1f}s = {n/el:.1f}Hz")
        if cf: cf.close(); print(f"  Saved: {logf}")

def c_list():
    print("\n=== Params ===")
    for k,p in sorted(PM.items()):
        print(f"  {k:10s} {p.nm:8s} 0x{p.adr:04X} [{p.u:5s}] {p.bid}{('  '+p.desc) if p.desc else ''}")
    print("\n=== Presets ===")
    for n,(ks,d) in PRESETS.items(): print(f"  --{n:8s} {d}\n             {','.join(ks)}\n")

# ═════════ Main ═════════
def main():
    ap=argparse.ArgumentParser(description='BMW DDE5 M57 v2.0')
    ap.add_argument('--port','-p',default='/dev/ttyUSB0')
    ap.add_argument('--baud',type=int,default=9600)
    ap.add_argument('--fast-init',action='store_true')
    ap.add_argument('--debug','-d',action='store_true')
    ap.add_argument('--ident',action='store_true')
    ap.add_argument('--faults',action='store_true')
    ap.add_argument('--clear-faults',action='store_true')
    for n in PRESETS: ap.add_argument(f'--{n}',action='store_true')
    ap.add_argument('--params',type=str,help='rpm,boost,...')
    ap.add_argument('--all',action='store_true')
    ap.add_argument('--log',type=str,help='CSV file')
    ap.add_argument('--list',action='store_true')
    a=ap.parse_args()
    if a.debug: logging.getLogger().setLevel(logging.DEBUG)
    if a.list: c_list(); return
    pn=tb=None; keys=None
    for n in PRESETS:
        if getattr(a,n,False): keys,_=PRESETS[n]; pn=n; tb=(n=='turbo'); break
    if a.params: keys=[x.strip() for x in a.params.split(',')]
    if not any([a.ident,a.faults,a.clear_faults,keys,a.all]): ap.print_help(); return
    # EdiabasLib: KWP2000 BMW (0x010C) uses parity=NONE (8N1), NOT 8E1!
    ser=serial.Serial(a.port,a.baud,8,serial.PARITY_NONE,1,timeout=0.5)
    # K+DCAN cable: DTR selects mode! DTR=false→K-Line, DTR=true→D-CAN
    # pyserial defaults DTR=true → WRONG! Must set false for K-Line
    ser.dtr=False
    ser.rts=False
    time.sleep(0.1)  # let cable settle after mode switch
    # Fast-init: only if needed (EdiabasLib skips it for KWP2000 BMW)
    if a.fast_init:
        ser.dtr=True
        ser.break_condition=True;time.sleep(.025)
        ser.break_condition=False;time.sleep(.025)
        ser.dtr=False
    ser.reset_input_buffer()
    try:
        import subprocess; subprocess.run(['bash','-c',f'echo 1>/sys/bus/usb-serial/devices/{a.port.split("/")[-1]}/latency_timer'],capture_output=True,timeout=2)
    except: pass
    k=KWP(ser); log.info(f"{a.port}@{a.baud}")
    if not k.start(): log.warning("Session fail — try --fast-init / --baud 10400")
    try:
        if a.ident: c_ident(k)
        if a.faults: c_faults(k)
        if a.clear_faults: print("OK ✓" if k.clear() else "Fail")
        if a.all: c_once(k,list(PM.keys()))
        elif keys:
            lf=a.log or (f"dde5_{pn or'x'}_{datetime.now():%Y%m%d_%H%M%S}.csv" if pn else None)
            if pn or a.log: c_live(k,keys,lf,tb)
            else: c_once(k,keys)
    except serial.SerialException as e: log.error(e)
    except KeyboardInterrupt: pass
    finally: ser.close()

if __name__=='__main__': main()
