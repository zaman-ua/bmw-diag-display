# BMW DDE Diagnostic Tool (Python / K-Line)

Консольный инструмент для диагностики дизельных BMW (M47/M57) через K+DCAN кабель на Linux.

Параметры извлечены из PRG-файлов BMW EDIABAS путём реверс-инжиниринга BEST1 байткода (XOR 0xF7 → BetriebswTab).

## Поддерживаемые ECU

| SGBD файл | ECU | Двигатель | Автомобили |
|-----------|-----|-----------|------------|
| d40m57a1 | DDE4 | M57 | E39 530d (ранний) |
| d50m57a0 | DDE5 | M57TU | E39/E46 530d/330d |
| d50m57b1 | DDE5 | M57TU | **E53 X5 3.0d** |
| d50m57c0 | DDE5 | M57TU | E60 530d (pre-LCI) |
| d60m57a0 | DDE6 | M57TU2 | E60/E90 530d/325d LCI |
| d62m57a0 | DDE6.2 | M57TU2TOP | E60 535d bi-turbo |
| d50m47a | DDE5 | M47TU | E46 320d |
| d50m47b1 | DDE5 | M47TU | E46/E83 320d EU4 |
| d60m47a0 | DDE6 | M47TU2 | E90 320d |

## Протокол

```
KWP2000 over K-Line (ISO 14230)
Baud: 9600 (или 10400), 8E1
ECU addr: 0x12 (DDE), Tester: 0xF1

Batch запрос (до 10 параметров за раз):
  TX: B8 12 F1 LEN 2C 10 [ADR1_H ADR1_L] [ADR2_H ADR2_L] ... CHK
  RX: B8 F1 12 LEN 6C 10 [VAL1_H VAL1_L] [VAL2_H VAL2_L] ... CHK

Формула: physical_value = raw_uint16 × FACT_A + FACT_B
```

## Требования

```bash
pip install pyserial
```

принудительно
```bash
python3 -m pip install pyserial --break-system-packages

```


K+DCAN кабель (FTDI FT232RL). Переключатель **ВЛЕВО** (K-Line).

## Файлы

| Файл | Описание |
|------|----------|
| `bmw_dde5_v2.py` | Основной скрипт диагностики с пресетами и CSV-логированием |
| `dde_params_db.py` | База параметров для всех вариантов DDE4/5/6 (M47/M57) |
| `dde_parameters_all.csv` | Полный список 788 параметров со всеми адресами |
| `prg_extractor.py` | Утилита для извлечения параметров из любого PRG файла |

## Быстрый старт

```bash
# Список всех параметров и пресетов
python3 bmw_dde5_v2.py --list

# Тест связи с ECU (зажигание включено, кабель подключен)
sudo python3 bmw_dde5_v2.py -d -p /dev/ttyUSB0 --ident

# Чтение ошибок DDE
sudo python3 bmw_dde5_v2.py -p /dev/ttyUSB0 --faults

# Все параметры (однократное чтение)
sudo python3 bmw_dde5_v2.py -p /dev/ttyUSB0 --all
```

## Пресеты для live-мониторинга

### Диагностика турбины (`--turbo`)

Самый полезный пресет. Показывает целевой vs фактический воздух — ключ к проблемам турбины.

```bash
# Live-монитор в консоли
sudo python3 bmw_dde5_v2.py -p /dev/ttyUSB0 --turbo

# С записью в CSV (для графиков)
sudo python3 bmw_dde5_v2.py -p /dev/ttyUSB0 --turbo --log turbo_test.csv
```

Вывод:
```
   sec     RPM  Boost    Atm AirAct AirTgt    MAF  Pedal  CoolT   IntT   Batt  ΔAir  RelBst
          rpm    hPa    hPa   mg/H   mg/H   Kg/h      %     °C     °C      V  mg/H     hPa
─────────────────────────────────────────────────────────────────────────────────────────────
   3.2   2800   1850   1013  450.2  480.5  120.3   100  85.2   32.1  13.85   -30✓    837
   3.6   3400   2100   1013  530.0  650.8  152.1   100  85.5   34.2  13.75  -121✗   1087
```

- **ΔAir** = AirActual − AirTarget (mg/Hub):
  - `✓` < 50: турбина дует нормально
  - `⚠` 50-100: начинает отставать
  - `✗` > 100: турбина недодувает — проблема!

- **RelBst** = Boost − Atm = относительный наддув (hPa)

### Топливная система (`--rail`)

```bash
sudo python3 bmw_dde5_v2.py -p /dev/ttyUSB0 --rail --log rail_test.csv
```

Показывает: Rail actual vs target, впрыск (mg/cyc), температура топлива.

### Неравномерность (`--rough`)

```bash
sudo python3 bmw_dde5_v2.py -p /dev/ttyUSB0 --rough
```

RPM по каждому из 6 цилиндров — для диагностики форсунок и компрессии.

### Основные параметры (`--engine`)

```bash
sudo python3 bmw_dde5_v2.py -p /dev/ttyUSB0 --engine
```

RPM, температура, наддув, Rail, момент, скорость.

### Произвольный набор

```bash
sudo python3 bmw_dde5_v2.py -p /dev/ttyUSB0 --params rpm,boost,rail,coolant,pedal
```

## Как анализировать CSV-логи

```bash
# Заезд: 3-4 передача, с низов газ в пол
sudo python3 bmw_dde5_v2.py -p /dev/ttyUSB0 --turbo --log drive.csv

# Потом открыть drive.csv в LibreOffice Calc / Excel
# Построить графики: AirActual и AirTarget по времени
# Где линии расходятся — там проблема турбины
```

## Возможные проблемы

| Симптом | Решение |
|---------|---------|
| No response | Проверь переключатель кабеля (LEFT), зажигание ON |
| Session fail | `--fast-init` или `--baud 10400` |
| Мусор в ответе | Проверь пarity (8E1), попробуй другой baud |
| FTDI не видит | `ls /dev/ttyUSB*`, проверь драйвер `lsmod \| grep ftdi` |

## Как это работает

1. PRG файлы BMW EDIABAS содержат BEST1 байткод (XOR 0xF7)
2. Внутри — таблица `BetriebswTab` с Bosch-идентификаторами (напр. `Eng_nAvrg`)
3. Каждый идентификатор имеет ADR (адрес памяти ECU), FACT_A, FACT_B, единицы
4. Скрипт отправляет KWP2000 `$2C $10` с набором ADR → ECU отвечает значениями
5. Значения пересчитываются: `physical = raw × FACT_A + FACT_B`

## Про LADEDRUCK_SOLL

В DDE5 (M57TU) нет отдельного параметра «целевой наддув в hPa». Bosch перешёл от управления **давлением** к управлению **массой воздуха**. Целевое значение — это `AirCtl_mDesVal` (mg/Hub). Сравнивая его с `AFSCD_mAirPerCyl` (факт. воздух) получаем ту же диагностическую информацию.
