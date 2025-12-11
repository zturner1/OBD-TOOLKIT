#!/usr/bin/env python3
"""
Generate realistic simulated OBD log files for testing and demonstration.
Creates both JSON and CSV formats for each scenario.
"""

import json
import csv
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
SAMPLE_INTERVAL_MS = 250  # 250ms between samples
DURATION_MINUTES = 8  # 8 minute drive
TOTAL_SAMPLES = int((DURATION_MINUTES * 60 * 1000) / SAMPLE_INTERVAL_MS)  # 1920 samples

# PID names in order
PID_NAMES = [
    "RPM", "SPEED", "COOLANT_TEMP", "ENGINE_LOAD", "THROTTLE_POS",
    "INTAKE_TEMP", "MAF", "FUEL_PRESSURE", "TIMING_ADVANCE",
    "SHORT_FUEL_TRIM_1", "LONG_FUEL_TRIM_1", "O2_B1S1", "FUEL_STATUS",
    "RUN_TIME", "DISTANCE_W_MIL", "BAROMETRIC_PRESSURE",
    "CONTROL_MODULE_VOLTAGE", "AMBIENT_AIR_TEMP", "FUEL_LEVEL"
]

def add_noise(value, std_dev, min_val=None, max_val=None):
    """Add Gaussian noise to a value, optionally clamping to range."""
    noisy = value + random.gauss(0, std_dev)
    if min_val is not None:
        noisy = max(min_val, noisy)
    if max_val is not None:
        noisy = min(max_val, noisy)
    return round(noisy, 2)

def smooth_transition(current, target, rate=0.1):
    """Smoothly transition from current to target value."""
    return current + (target - rate) * rate if abs(current - target) > 0.1 else target

def get_o2_oscillation(time_s, scenario="normal"):
    """Generate realistic O2 sensor oscillation."""
    if scenario == "normal":
        # Normal oscillation 0.1-0.9V at ~1Hz
        base = 0.5 + 0.35 * math.sin(2 * math.pi * 1.0 * time_s)
        return add_noise(base, 0.05, 0.1, 0.9)
    elif scenario == "misfire":
        # Slower, more erratic oscillation with lean bias
        base = 0.35 + 0.25 * math.sin(2 * math.pi * 0.5 * time_s)
        if random.random() < 0.2:  # Occasional stuck lean
            return add_noise(0.25, 0.05, 0.1, 0.4)
        return add_noise(base, 0.08, 0.1, 0.9)
    else:
        return add_noise(0.5 + 0.35 * math.sin(2 * math.pi * 1.0 * time_s), 0.05, 0.1, 0.9)

def calculate_maf(rpm, load, scenario="normal"):
    """Calculate MAF based on RPM and load with correlation."""
    base_maf = (rpm / 1000) * (load / 100) * 12.0
    if scenario == "misfire":
        base_maf *= 0.92  # Slightly lower due to misfire
    return add_noise(base_maf, 0.3, 0.5, 100)

def get_drive_phase(time_s, scenario):
    """Determine driving phase based on time."""
    if time_s < 30:
        return "cold_start"
    elif time_s < 60:
        return "warmup_idle"
    elif time_s < 150:
        return "residential"
    elif time_s < 210:
        return "acceleration"
    elif time_s < 330:
        return "highway"
    elif time_s < 390:
        return "deceleration"
    elif time_s < 450:
        return "residential_2"
    else:
        return "parking"

def generate_normal_commute_sample(sample_idx, prev_values, start_time):
    """Generate a single sample for normal commute scenario."""
    time_s = sample_idx * SAMPLE_INTERVAL_MS / 1000
    phase = get_drive_phase(time_s, "normal")

    # Initialize with previous values or defaults
    if prev_values is None:
        prev_values = {
            "RPM": 0, "SPEED": 0, "COOLANT_TEMP": 22, "ENGINE_LOAD": 0,
            "THROTTLE_POS": 0, "INTAKE_TEMP": 20, "MAF": 0, "FUEL_PRESSURE": 0,
            "TIMING_ADVANCE": 0, "SHORT_FUEL_TRIM_1": 0, "LONG_FUEL_TRIM_1": 0,
            "O2_B1S1": 0.45, "FUEL_STATUS": 1, "RUN_TIME": 0, "DISTANCE_W_MIL": 0,
            "BAROMETRIC_PRESSURE": 101.3, "CONTROL_MODULE_VOLTAGE": 12.6,
            "AMBIENT_AIR_TEMP": 18, "FUEL_LEVEL": 72.5
        }

    values = {}

    # Phase-specific base values
    if phase == "cold_start":
        target_rpm = 1200 - (time_s * 10)  # Dropping from 1200
        target_speed = 0
        target_load = 28
        target_throttle = 14
        coolant_rise = 0.15  # Slow initial rise
    elif phase == "warmup_idle":
        target_rpm = 850
        target_speed = 0
        target_load = 22
        target_throttle = 12
        coolant_rise = 0.12
    elif phase == "residential":
        # Stop and go pattern
        cycle_pos = (time_s - 60) % 30
        if cycle_pos < 10:  # Accelerating
            target_rpm = 1500 + cycle_pos * 100
            target_speed = cycle_pos * 4
            target_load = 35 + cycle_pos * 2
            target_throttle = 20 + cycle_pos * 2
        elif cycle_pos < 20:  # Cruising
            target_rpm = 2000
            target_speed = 40
            target_load = 30
            target_throttle = 18
        else:  # Braking/stopping
            target_rpm = 2000 - (cycle_pos - 20) * 120
            target_speed = 40 - (cycle_pos - 20) * 4
            target_load = 15
            target_throttle = 5
        coolant_rise = 0.08
    elif phase == "acceleration":
        progress = (time_s - 150) / 60
        target_rpm = 2000 + progress * 2500
        target_speed = 40 + progress * 80
        target_load = 55 + progress * 15
        target_throttle = 45 + progress * 20
        coolant_rise = 0.05
    elif phase == "highway":
        target_rpm = 2500 + math.sin(time_s * 0.1) * 200
        target_speed = 110 + math.sin(time_s * 0.05) * 10
        target_load = 40 + math.sin(time_s * 0.08) * 5
        target_throttle = 30 + math.sin(time_s * 0.08) * 5
        coolant_rise = 0.01
    elif phase == "deceleration":
        progress = (time_s - 330) / 60
        target_rpm = 2500 - progress * 1000
        target_speed = 110 - progress * 60
        target_load = 20 - progress * 5
        target_throttle = 10 - progress * 5
        coolant_rise = 0.02
    elif phase == "residential_2":
        cycle_pos = (time_s - 390) % 25
        if cycle_pos < 8:
            target_rpm = 1200 + cycle_pos * 80
            target_speed = cycle_pos * 4
            target_load = 28 + cycle_pos * 2
            target_throttle = 15 + cycle_pos * 2
        elif cycle_pos < 18:
            target_rpm = 1800
            target_speed = 35
            target_load = 28
            target_throttle = 16
        else:
            target_rpm = 1800 - (cycle_pos - 18) * 140
            target_speed = 35 - (cycle_pos - 18) * 5
            target_load = 15
            target_throttle = 5
        coolant_rise = 0.02
    else:  # parking
        progress = (time_s - 450) / 30
        target_rpm = max(800, 1200 - progress * 400)
        target_speed = max(0, 20 - progress * 20)
        target_load = 20
        target_throttle = 12
        coolant_rise = 0.01

    # Smooth transitions
    values["RPM"] = add_noise(
        prev_values["RPM"] + (target_rpm - prev_values["RPM"]) * 0.15,
        20, 0, 7000
    )
    values["SPEED"] = add_noise(
        prev_values["SPEED"] + (target_speed - prev_values["SPEED"]) * 0.12,
        0.5, 0, 200
    )
    values["ENGINE_LOAD"] = add_noise(
        prev_values["ENGINE_LOAD"] + (target_load - prev_values["ENGINE_LOAD"]) * 0.1,
        1.5, 0, 100
    )
    values["THROTTLE_POS"] = add_noise(
        prev_values["THROTTLE_POS"] + (target_throttle - prev_values["THROTTLE_POS"]) * 0.2,
        0.8, 0, 100
    )

    # Temperature progression
    if prev_values["COOLANT_TEMP"] < 90:
        values["COOLANT_TEMP"] = min(92, prev_values["COOLANT_TEMP"] + coolant_rise)
    else:
        values["COOLANT_TEMP"] = add_noise(90, 1.5, 88, 95)

    values["INTAKE_TEMP"] = add_noise(
        18 + (values["COOLANT_TEMP"] - 20) * 0.2,
        0.5, 15, 50
    )

    # Calculated values
    values["MAF"] = calculate_maf(values["RPM"], values["ENGINE_LOAD"])
    values["FUEL_PRESSURE"] = add_noise(350 + values["ENGINE_LOAD"] * 1.2, 3, 300, 500)
    values["TIMING_ADVANCE"] = add_noise(
        10 + (values["RPM"] / 1000) * 5 - (values["ENGINE_LOAD"] / 100) * 8,
        0.8, -5, 40
    )

    # Fuel trims - healthy engine, small variations
    values["SHORT_FUEL_TRIM_1"] = add_noise(0, 3, -10, 10)
    values["LONG_FUEL_TRIM_1"] = add_noise(prev_values["LONG_FUEL_TRIM_1"], 0.1, -5, 5)

    # O2 sensor
    values["O2_B1S1"] = get_o2_oscillation(time_s, "normal")

    # Static/slow-changing values
    values["FUEL_STATUS"] = 2  # Closed loop
    values["RUN_TIME"] = round(time_s, 1)
    values["DISTANCE_W_MIL"] = 0  # No MIL
    values["BAROMETRIC_PRESSURE"] = add_noise(101.3, 0.1, 99, 103)
    values["CONTROL_MODULE_VOLTAGE"] = add_noise(14.1, 0.1, 13.5, 14.5)
    values["AMBIENT_AIR_TEMP"] = add_noise(18, 0.1, 17, 19)
    values["FUEL_LEVEL"] = round(72.5 - time_s * 0.002, 1)  # Slight decrease

    timestamp = start_time + timedelta(milliseconds=sample_idx * SAMPLE_INTERVAL_MS)

    return {
        "timestamp": timestamp.isoformat(timespec='milliseconds'),
        "values": values
    }, values

def generate_bad_spark_plug_sample(sample_idx, prev_values, start_time):
    """Generate sample with misfire/bad spark plug symptoms."""
    time_s = sample_idx * SAMPLE_INTERVAL_MS / 1000
    phase = get_drive_phase(time_s, "misfire")

    if prev_values is None:
        prev_values = {
            "RPM": 0, "SPEED": 0, "COOLANT_TEMP": 25, "ENGINE_LOAD": 0,
            "THROTTLE_POS": 0, "INTAKE_TEMP": 22, "MAF": 0, "FUEL_PRESSURE": 0,
            "TIMING_ADVANCE": 0, "SHORT_FUEL_TRIM_1": 8, "LONG_FUEL_TRIM_1": 12,
            "O2_B1S1": 0.35, "FUEL_STATUS": 1, "RUN_TIME": 0, "DISTANCE_W_MIL": 15,
            "BAROMETRIC_PRESSURE": 101.2, "CONTROL_MODULE_VOLTAGE": 14.0,
            "AMBIENT_AIR_TEMP": 19, "FUEL_LEVEL": 68
        }

    values = {}

    # Similar driving pattern but with misfire effects
    if phase == "cold_start":
        target_rpm = 1100 - (time_s * 8)
        target_speed = 0
        target_load = 32  # Higher due to compensation
        target_throttle = 15
        coolant_rise = 0.18
    elif phase == "warmup_idle" or phase == "parking":
        target_rpm = 780
        target_speed = 0
        target_load = 28
        target_throttle = 13
        coolant_rise = 0.1
    elif phase == "residential" or phase == "residential_2":
        cycle_pos = ((time_s - 60) if phase == "residential" else (time_s - 390)) % 30
        if cycle_pos < 10:
            target_rpm = 1400 + cycle_pos * 90
            target_speed = cycle_pos * 3.5
            target_load = 38 + cycle_pos * 2
            target_throttle = 22 + cycle_pos * 2
        elif cycle_pos < 20:
            target_rpm = 1900
            target_speed = 38
            target_load = 32
            target_throttle = 19
        else:
            target_rpm = 1900 - (cycle_pos - 20) * 110
            target_speed = 38 - (cycle_pos - 20) * 3.8
            target_load = 18
            target_throttle = 6
        coolant_rise = 0.08
    elif phase == "acceleration":
        progress = (time_s - 150) / 60
        target_rpm = 1800 + progress * 2200  # Slower acceleration
        target_speed = 35 + progress * 70
        target_load = 58 + progress * 12
        target_throttle = 48 + progress * 18
        coolant_rise = 0.05
    elif phase == "highway":
        # Smoother at highway - misfire less noticeable
        target_rpm = 2400 + math.sin(time_s * 0.1) * 150
        target_speed = 105 + math.sin(time_s * 0.05) * 8
        target_load = 42 + math.sin(time_s * 0.08) * 4
        target_throttle = 32 + math.sin(time_s * 0.08) * 4
        coolant_rise = 0.01
    else:  # deceleration
        progress = (time_s - 330) / 60
        target_rpm = 2400 - progress * 900
        target_speed = 105 - progress * 55
        target_load = 22 - progress * 5
        target_throttle = 12 - progress * 5
        coolant_rise = 0.02

    # Add misfire effects - RPM drops and instability
    rpm_base = prev_values["RPM"] + (target_rpm - prev_values["RPM"]) * 0.12

    # Misfire events - more frequent at idle/low speed
    if phase in ["warmup_idle", "parking", "cold_start"]:
        rpm_noise_std = 80  # High instability
        if random.random() < 0.15:  # 15% chance of misfire drop
            rpm_base -= random.uniform(80, 180)
    elif phase in ["residential", "residential_2"]:
        rpm_noise_std = 50
        if random.random() < 0.08:
            rpm_base -= random.uniform(60, 120)
    else:
        rpm_noise_std = 30  # More stable at highway
        if random.random() < 0.03:
            rpm_base -= random.uniform(40, 80)

    values["RPM"] = add_noise(rpm_base, rpm_noise_std, 500, 6500)
    values["SPEED"] = add_noise(
        prev_values["SPEED"] + (target_speed - prev_values["SPEED"]) * 0.1,
        0.6, 0, 180
    )
    values["ENGINE_LOAD"] = add_noise(
        prev_values["ENGINE_LOAD"] + (target_load - prev_values["ENGINE_LOAD"]) * 0.1,
        4, 0, 100  # More erratic
    )
    values["THROTTLE_POS"] = add_noise(
        prev_values["THROTTLE_POS"] + (target_throttle - prev_values["THROTTLE_POS"]) * 0.18,
        1.2, 0, 100
    )

    # Temperature - slightly elevated due to inefficiency
    if prev_values["COOLANT_TEMP"] < 94:
        values["COOLANT_TEMP"] = min(96, prev_values["COOLANT_TEMP"] + coolant_rise * 1.1)
    else:
        values["COOLANT_TEMP"] = add_noise(94, 1.8, 90, 98)

    values["INTAKE_TEMP"] = add_noise(22 + (values["COOLANT_TEMP"] - 22) * 0.22, 0.6, 18, 55)

    # MAF - slightly lower due to misfire
    values["MAF"] = calculate_maf(values["RPM"], values["ENGINE_LOAD"], "misfire")
    values["FUEL_PRESSURE"] = add_noise(345 + values["ENGINE_LOAD"] * 1.1, 4, 290, 480)

    # Timing - retarded due to misfire
    base_timing = 6 + (values["RPM"] / 1000) * 4 - (values["ENGINE_LOAD"] / 100) * 10
    values["TIMING_ADVANCE"] = add_noise(base_timing, 1.5, -8, 35)

    # Fuel trims - positive bias (lean from misfire)
    target_stft = 12 + random.gauss(0, 5)
    values["SHORT_FUEL_TRIM_1"] = add_noise(
        prev_values["SHORT_FUEL_TRIM_1"] + (target_stft - prev_values["SHORT_FUEL_TRIM_1"]) * 0.15,
        4, -15, 25
    )
    # Long-term adapting high
    values["LONG_FUEL_TRIM_1"] = add_noise(
        min(18, prev_values["LONG_FUEL_TRIM_1"] + 0.01),
        0.3, 8, 20
    )

    # O2 sensor - erratic, lean-biased
    values["O2_B1S1"] = get_o2_oscillation(time_s, "misfire")

    values["FUEL_STATUS"] = 2
    values["RUN_TIME"] = round(time_s, 1)
    values["DISTANCE_W_MIL"] = round(15 + values["SPEED"] * time_s / 3600, 1)  # MIL is on
    values["BAROMETRIC_PRESSURE"] = add_noise(101.2, 0.1, 99, 103)
    values["CONTROL_MODULE_VOLTAGE"] = add_noise(14.0, 0.12, 13.4, 14.4)
    values["AMBIENT_AIR_TEMP"] = add_noise(19, 0.1, 18, 20)
    values["FUEL_LEVEL"] = round(68 - time_s * 0.003, 1)  # Higher consumption

    timestamp = start_time + timedelta(milliseconds=sample_idx * SAMPLE_INTERVAL_MS)

    return {
        "timestamp": timestamp.isoformat(timespec='milliseconds'),
        "values": values
    }, values

def generate_oil_problem_sample(sample_idx, prev_values, start_time):
    """Generate sample with oil/overheating problem symptoms."""
    time_s = sample_idx * SAMPLE_INTERVAL_MS / 1000
    phase = get_drive_phase(time_s, "oil")

    if prev_values is None:
        prev_values = {
            "RPM": 0, "SPEED": 0, "COOLANT_TEMP": 24, "ENGINE_LOAD": 0,
            "THROTTLE_POS": 0, "INTAKE_TEMP": 21, "MAF": 0, "FUEL_PRESSURE": 0,
            "TIMING_ADVANCE": 0, "SHORT_FUEL_TRIM_1": 2, "LONG_FUEL_TRIM_1": 5,
            "O2_B1S1": 0.45, "FUEL_STATUS": 1, "RUN_TIME": 0, "DISTANCE_W_MIL": 85,
            "BAROMETRIC_PRESSURE": 101.1, "CONTROL_MODULE_VOLTAGE": 14.2,
            "AMBIENT_AIR_TEMP": 20, "FUEL_LEVEL": 70.8
        }

    values = {}

    # Progressive overheating factor (0 to 1 over the drive)
    overheat_factor = min(1.0, time_s / 400)

    # Normal driving pattern
    if phase == "cold_start":
        target_rpm = 1150 - (time_s * 9)
        target_speed = 0
        target_load = 30 + overheat_factor * 5  # Increasing friction
        target_throttle = 14
    elif phase == "warmup_idle" or phase == "parking":
        target_rpm = 820 + overheat_factor * 50  # ECU compensating
        target_speed = 0
        target_load = 25 + overheat_factor * 8
        target_throttle = 12 + overheat_factor * 2
    elif phase == "residential" or phase == "residential_2":
        cycle_pos = ((time_s - 60) if phase == "residential" else (time_s - 390)) % 30
        if cycle_pos < 10:
            target_rpm = 1500 + cycle_pos * 95
            target_speed = cycle_pos * 4
            target_load = 38 + cycle_pos * 2 + overheat_factor * 8
            target_throttle = 21 + cycle_pos * 2
        elif cycle_pos < 20:
            target_rpm = 2000
            target_speed = 40
            target_load = 32 + overheat_factor * 10
            target_throttle = 18 + overheat_factor * 3
        else:
            target_rpm = 2000 - (cycle_pos - 20) * 115
            target_speed = 40 - (cycle_pos - 20) * 4
            target_load = 18 + overheat_factor * 5
            target_throttle = 6
    elif phase == "acceleration":
        progress = (time_s - 150) / 60
        target_rpm = 1900 + progress * 2400
        target_speed = 38 + progress * 75
        target_load = 58 + progress * 14 + overheat_factor * 10
        target_throttle = 48 + progress * 18
    elif phase == "highway":
        target_rpm = 2450 + math.sin(time_s * 0.1) * 180
        target_speed = 108 + math.sin(time_s * 0.05) * 8
        target_load = 44 + math.sin(time_s * 0.08) * 4 + overheat_factor * 12
        target_throttle = 32 + math.sin(time_s * 0.08) * 4 + overheat_factor * 5
    else:  # deceleration
        progress = (time_s - 330) / 60
        target_rpm = 2450 - progress * 950
        target_speed = 108 - progress * 58
        target_load = 22 + overheat_factor * 8
        target_throttle = 12

    values["RPM"] = add_noise(
        prev_values["RPM"] + (target_rpm - prev_values["RPM"]) * 0.14,
        25 + overheat_factor * 15, 0, 6800
    )
    values["SPEED"] = add_noise(
        prev_values["SPEED"] + (target_speed - prev_values["SPEED"]) * 0.11,
        0.5, 0, 190
    )
    values["ENGINE_LOAD"] = add_noise(
        prev_values["ENGINE_LOAD"] + (target_load - prev_values["ENGINE_LOAD"]) * 0.12,
        2 + overheat_factor * 2, 0, 100
    )
    values["THROTTLE_POS"] = add_noise(
        prev_values["THROTTLE_POS"] + (target_throttle - prev_values["THROTTLE_POS"]) * 0.18,
        1.0, 0, 100
    )

    # KEY: Temperature steadily climbing - never stabilizes
    # Normal thermostat would stabilize at 90C, but this keeps rising
    if time_s < 120:
        # Initial warmup - faster than normal
        target_temp = 24 + time_s * 0.6
    else:
        # Continues rising past normal operating temp
        target_temp = 96 + (time_s - 120) * 0.04  # Gradual rise to ~108C

    values["COOLANT_TEMP"] = add_noise(
        min(112, prev_values["COOLANT_TEMP"] + (target_temp - prev_values["COOLANT_TEMP"]) * 0.08),
        0.5, 20, 115
    )

    # Intake temp also elevated
    values["INTAKE_TEMP"] = add_noise(
        21 + (values["COOLANT_TEMP"] - 20) * 0.35,
        0.6, 18, 60
    )

    values["MAF"] = calculate_maf(values["RPM"], values["ENGINE_LOAD"])
    values["FUEL_PRESSURE"] = add_noise(
        345 + values["ENGINE_LOAD"] * 1.15 - overheat_factor * 15,
        4, 280, 490
    )

    # Timing progressively retarded as engine heats up
    base_timing = 11 - overheat_factor * 6 + (values["RPM"] / 1000) * 4.5 - (values["ENGINE_LOAD"] / 100) * 9
    values["TIMING_ADVANCE"] = add_noise(base_timing, 1.2, -10, 38)

    # Fuel trims trending positive (running lean as engine heats up)
    values["SHORT_FUEL_TRIM_1"] = add_noise(
        prev_values["SHORT_FUEL_TRIM_1"] * 0.95 + (5 + overheat_factor * 10) * 0.05,
        3, -12, 22
    )
    values["LONG_FUEL_TRIM_1"] = add_noise(
        min(15, prev_values["LONG_FUEL_TRIM_1"] + 0.008),
        0.2, 3, 18
    )

    values["O2_B1S1"] = get_o2_oscillation(time_s, "normal")

    values["FUEL_STATUS"] = 2
    values["RUN_TIME"] = round(time_s, 1)
    values["DISTANCE_W_MIL"] = round(85 + values["SPEED"] * time_s / 3600, 1)
    values["BAROMETRIC_PRESSURE"] = add_noise(101.1, 0.1, 99, 103)

    # Voltage slightly lower under stress
    values["CONTROL_MODULE_VOLTAGE"] = add_noise(14.0 - overheat_factor * 0.3, 0.12, 13.2, 14.4)
    values["AMBIENT_AIR_TEMP"] = add_noise(20, 0.1, 19, 21)
    values["FUEL_LEVEL"] = round(70.8 - time_s * 0.0025, 1)

    timestamp = start_time + timedelta(milliseconds=sample_idx * SAMPLE_INTERVAL_MS)

    return {
        "timestamp": timestamp.isoformat(timespec='milliseconds'),
        "values": values
    }, values

def generate_esc_fault_sample(sample_idx, prev_values, start_time):
    """Generate sample with ESC/wheel speed sensor fault symptoms."""
    time_s = sample_idx * SAMPLE_INTERVAL_MS / 1000
    phase = get_drive_phase(time_s, "esc")

    if prev_values is None:
        prev_values = {
            "RPM": 0, "SPEED": 0, "COOLANT_TEMP": 23, "ENGINE_LOAD": 0,
            "THROTTLE_POS": 0, "INTAKE_TEMP": 21, "MAF": 0, "FUEL_PRESSURE": 0,
            "TIMING_ADVANCE": 0, "SHORT_FUEL_TRIM_1": 1, "LONG_FUEL_TRIM_1": 0.5,
            "O2_B1S1": 0.45, "FUEL_STATUS": 1, "RUN_TIME": 0, "DISTANCE_W_MIL": 0,
            "BAROMETRIC_PRESSURE": 101.0, "CONTROL_MODULE_VOLTAGE": 14.1,
            "AMBIENT_AIR_TEMP": 21, "FUEL_LEVEL": 71.2
        }

    values = {}

    # Normal driving - ESC fault doesn't affect engine much
    if phase == "cold_start":
        target_rpm = 1180 - (time_s * 10)
        target_speed = 0
        target_load = 27
        target_throttle = 14
        coolant_rise = 0.15
    elif phase == "warmup_idle" or phase == "parking":
        target_rpm = 840
        target_speed = 0
        target_load = 21
        target_throttle = 12
        coolant_rise = 0.1
    elif phase == "residential" or phase == "residential_2":
        cycle_pos = ((time_s - 60) if phase == "residential" else (time_s - 390)) % 30
        if cycle_pos < 10:
            target_rpm = 1500 + cycle_pos * 100
            target_speed = cycle_pos * 4.2
            target_load = 35 + cycle_pos * 2
            target_throttle = 20 + cycle_pos * 2
        elif cycle_pos < 20:
            target_rpm = 2050
            target_speed = 42
            target_load = 30
            target_throttle = 18
        else:
            target_rpm = 2050 - (cycle_pos - 20) * 125
            target_speed = 42 - (cycle_pos - 20) * 4.2
            target_load = 15
            target_throttle = 5
        coolant_rise = 0.08
    elif phase == "acceleration":
        progress = (time_s - 150) / 60
        target_rpm = 2050 + progress * 2600
        target_speed = 42 + progress * 82
        target_load = 56 + progress * 15
        target_throttle = 46 + progress * 20
        coolant_rise = 0.04
    elif phase == "highway":
        target_rpm = 2550 + math.sin(time_s * 0.1) * 200
        target_speed = 115 + math.sin(time_s * 0.05) * 10
        target_load = 41 + math.sin(time_s * 0.08) * 5
        target_throttle = 31 + math.sin(time_s * 0.08) * 5
        coolant_rise = 0.01
    else:  # deceleration
        progress = (time_s - 330) / 60
        target_rpm = 2550 - progress * 1050
        target_speed = 115 - progress * 62
        target_load = 20 - progress * 5
        target_throttle = 10 - progress * 5
        coolant_rise = 0.02

    values["RPM"] = add_noise(
        prev_values["RPM"] + (target_rpm - prev_values["RPM"]) * 0.15,
        22, 0, 7000
    )

    # SPEED - KEY SYMPTOM: intermittent glitches from faulty wheel speed sensor
    calculated_speed = prev_values["SPEED"] + (target_speed - prev_values["SPEED"]) * 0.12

    # Wheel speed sensor glitch - occasional dropouts or spikes
    if random.random() < 0.03:  # 3% chance of glitch
        glitch_type = random.choice(["dropout", "spike", "stuck"])
        if glitch_type == "dropout":
            calculated_speed = 0  # Sensor reads 0 briefly
        elif glitch_type == "spike":
            calculated_speed = calculated_speed + random.uniform(15, 30)  # Spike up
        else:  # stuck
            calculated_speed = prev_values["SPEED"]  # Stuck at previous value

    values["SPEED"] = add_noise(calculated_speed, 0.8, 0, 220)

    values["ENGINE_LOAD"] = add_noise(
        prev_values["ENGINE_LOAD"] + (target_load - prev_values["ENGINE_LOAD"]) * 0.1,
        1.5, 0, 100
    )
    values["THROTTLE_POS"] = add_noise(
        prev_values["THROTTLE_POS"] + (target_throttle - prev_values["THROTTLE_POS"]) * 0.2,
        0.8, 0, 100
    )

    # Normal temperature behavior
    if prev_values["COOLANT_TEMP"] < 91:
        values["COOLANT_TEMP"] = min(93, prev_values["COOLANT_TEMP"] + coolant_rise)
    else:
        values["COOLANT_TEMP"] = add_noise(91, 1.5, 88, 95)

    values["INTAKE_TEMP"] = add_noise(21 + (values["COOLANT_TEMP"] - 21) * 0.2, 0.5, 18, 50)

    values["MAF"] = calculate_maf(values["RPM"], values["ENGINE_LOAD"])
    values["FUEL_PRESSURE"] = add_noise(352 + values["ENGINE_LOAD"] * 1.2, 3, 305, 500)
    values["TIMING_ADVANCE"] = add_noise(
        11 + (values["RPM"] / 1000) * 5 - (values["ENGINE_LOAD"] / 100) * 8,
        0.8, -5, 40
    )

    # Normal fuel trims - engine is fine
    values["SHORT_FUEL_TRIM_1"] = add_noise(0, 2.5, -8, 8)
    values["LONG_FUEL_TRIM_1"] = add_noise(prev_values["LONG_FUEL_TRIM_1"], 0.1, -4, 4)

    values["O2_B1S1"] = get_o2_oscillation(time_s, "normal")

    values["FUEL_STATUS"] = 2
    values["RUN_TIME"] = round(time_s, 1)
    values["DISTANCE_W_MIL"] = 0  # Engine MIL not on (ESC is separate)
    values["BAROMETRIC_PRESSURE"] = add_noise(101.0, 0.1, 99, 103)

    # Occasional small voltage dip when ABS module tries to activate
    voltage = 14.1
    if random.random() < 0.02:
        voltage -= 0.3
    values["CONTROL_MODULE_VOLTAGE"] = add_noise(voltage, 0.1, 13.5, 14.5)

    values["AMBIENT_AIR_TEMP"] = add_noise(21, 0.1, 20, 22)
    values["FUEL_LEVEL"] = round(71.2 - time_s * 0.002, 1)

    timestamp = start_time + timedelta(milliseconds=sample_idx * SAMPLE_INTERVAL_MS)

    return {
        "timestamp": timestamp.isoformat(timespec='milliseconds'),
        "values": values
    }, values

def create_session_json(scenario_name, samples, start_time, end_time, vehicle_info, dtcs):
    """Create the full JSON session structure."""
    return {
        "session_id": f"sample_{scenario_name[:4]}",
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "vehicle": vehicle_info,
        "adapter": {
            "type": "ELM327",
            "port": "COM3",
            "firmware": "v1.5"
        },
        "protocol": "ISO 15765-4 (CAN 11/500)",
        "dtcs": dtcs,
        "sample_count": len(samples),
        "samples": samples,
        "analysis": [],
        "notes": f"Sample data: {scenario_name.replace('_', ' ').title()} scenario",
        "tags": ["sample", scenario_name]
    }

def write_csv(filepath, samples):
    """Write samples to CSV file."""
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp"] + PID_NAMES)
        for sample in samples:
            row = [sample["timestamp"]]
            for pid in PID_NAMES:
                row.append(sample["values"].get(pid, ""))
            writer.writerow(row)

def generate_scenario(name, generator_func, vehicle_info, dtcs):
    """Generate both JSON and CSV files for a scenario."""
    print(f"Generating {name}...")

    start_time = datetime(2024, 6, 15, 7, 30, 0)
    samples = []
    prev_values = None

    for i in range(TOTAL_SAMPLES):
        sample, prev_values = generator_func(i, prev_values, start_time)
        samples.append(sample)

    end_time = start_time + timedelta(milliseconds=TOTAL_SAMPLES * SAMPLE_INTERVAL_MS)

    # Create JSON
    session = create_session_json(name, samples, start_time, end_time, vehicle_info, dtcs)

    output_dir = Path(__file__).parent

    json_path = output_dir / f"{name}.json"
    with open(json_path, 'w') as f:
        json.dump(session, f, indent=2)
    print(f"  Created {json_path}")

    csv_path = output_dir / f"{name}.csv"
    write_csv(csv_path, samples)
    print(f"  Created {csv_path}")

def main():
    # Vehicle info for each scenario
    vehicles = {
        "normal_commute": {
            "vin": "1HGBH41JXMN109186",
            "manufacturer": "Honda",
            "country": "United States",
            "region": "North America",
            "model_year": 2021,
            "make": "Honda",
            "model": "Accord",
            "is_valid": True,
            "validation_errors": [],
            "assembly_plant": "M",
            "body_class": "Sedan",
            "engine_type": "2.0L Turbo",
            "fuel_type": "Gasoline",
            "drive_type": "FWD",
            "transmission": "CVT",
            "doors": 4
        },
        "bad_spark_plug": {
            "vin": "1FA6P8CF1L5101234",
            "manufacturer": "Ford",
            "country": "United States",
            "region": "North America",
            "model_year": 2020,
            "make": "Ford",
            "model": "Mustang",
            "is_valid": True,
            "validation_errors": [],
            "assembly_plant": "F",
            "body_class": "Coupe",
            "engine_type": "5.0L V8",
            "fuel_type": "Gasoline",
            "drive_type": "RWD",
            "transmission": "Manual",
            "doors": 2
        },
        "oil_problem": {
            "vin": "WVWZZZ3CZWE123456",
            "manufacturer": "Volkswagen",
            "country": "Germany",
            "region": "Europe",
            "model_year": 2019,
            "make": "Volkswagen",
            "model": "Golf",
            "is_valid": True,
            "validation_errors": [],
            "assembly_plant": "W",
            "body_class": "Hatchback",
            "engine_type": "2.0L TDI",
            "fuel_type": "Diesel",
            "drive_type": "FWD",
            "transmission": "DSG",
            "doors": 4
        },
        "esc_fault": {
            "vin": "WAUYGAFC5JN012345",
            "manufacturer": "Audi",
            "country": "Germany",
            "region": "Europe",
            "model_year": 2018,
            "make": "Audi",
            "model": "A4",
            "is_valid": True,
            "validation_errors": [],
            "assembly_plant": "N",
            "body_class": "Sedan",
            "engine_type": "2.0L TFSI",
            "fuel_type": "Gasoline",
            "drive_type": "AWD",
            "transmission": "S-tronic",
            "doors": 4
        }
    }

    # DTC configurations
    dtcs = {
        "normal_commute": {
            "stored_codes": [],
            "pending_codes": [],
            "permanent_codes": [],
            "mil_status": False,
            "dtc_count": 0,
            "timestamp": "2024-06-15T07:30:05"
        },
        "bad_spark_plug": {
            "stored_codes": [
                {
                    "code": "P0302",
                    "description": "Cylinder 2 Misfire Detected",
                    "category": "P",
                    "severity": "critical",
                    "dtc_type": "stored",
                    "possible_causes": ["Faulty spark plug", "Ignition coil failure", "Fuel injector issue"],
                    "symptoms": ["Rough idle", "Engine vibration", "Power loss"],
                    "suggested_actions": ["Replace spark plug", "Test ignition coil", "Check fuel injector"]
                }
            ],
            "pending_codes": [
                {
                    "code": "P0420",
                    "description": "Catalyst System Efficiency Below Threshold (Bank 1)",
                    "category": "P",
                    "severity": "warning",
                    "dtc_type": "pending",
                    "possible_causes": ["Worn catalytic converter", "Misfire damage"],
                    "symptoms": ["Check engine light", "Reduced fuel economy"],
                    "suggested_actions": ["Check for misfires first", "Inspect catalyst"]
                }
            ],
            "permanent_codes": [],
            "mil_status": True,
            "dtc_count": 2,
            "timestamp": "2024-06-15T07:30:05"
        },
        "oil_problem": {
            "stored_codes": [
                {
                    "code": "P0520",
                    "description": "Engine Oil Pressure Sensor/Switch Circuit",
                    "category": "P",
                    "severity": "critical",
                    "dtc_type": "stored",
                    "possible_causes": ["Low oil level", "Faulty oil pressure sensor", "Oil pump failure"],
                    "symptoms": ["Oil pressure warning light", "Engine noise", "Possible engine damage"],
                    "suggested_actions": ["Check oil level immediately", "Check oil pressure with mechanical gauge"]
                }
            ],
            "pending_codes": [
                {
                    "code": "P0116",
                    "description": "ECT Sensor Range/Performance",
                    "category": "P",
                    "severity": "warning",
                    "dtc_type": "pending",
                    "possible_causes": ["Thermostat stuck", "Cooling system issue", "Sensor problem"],
                    "symptoms": ["Poor fuel economy", "Overheating"],
                    "suggested_actions": ["Check thermostat", "Inspect cooling system"]
                }
            ],
            "permanent_codes": [],
            "mil_status": True,
            "dtc_count": 2,
            "timestamp": "2024-06-15T07:30:05"
        },
        "esc_fault": {
            "stored_codes": [
                {
                    "code": "C0035",
                    "description": "Left Front Wheel Speed Sensor Circuit",
                    "category": "C",
                    "severity": "critical",
                    "dtc_type": "stored",
                    "possible_causes": ["Faulty wheel speed sensor", "Wiring damage", "Wheel bearing issue"],
                    "symptoms": ["ABS warning light", "ESC/traction control disabled"],
                    "suggested_actions": ["Inspect wheel speed sensor", "Check wiring and connectors"]
                },
                {
                    "code": "C0561",
                    "description": "System Disabled - Information Stored",
                    "category": "C",
                    "severity": "warning",
                    "dtc_type": "stored",
                    "possible_causes": ["Related system fault", "Multiple sensor issues"],
                    "symptoms": ["ESC system disabled", "Warning light on"],
                    "suggested_actions": ["Diagnose underlying cause", "Clear codes after repair"]
                }
            ],
            "pending_codes": [],
            "permanent_codes": [],
            "mil_status": False,
            "dtc_count": 2,
            "timestamp": "2024-06-15T07:30:05"
        }
    }

    # Generators for each scenario
    generators = {
        "normal_commute": generate_normal_commute_sample,
        "bad_spark_plug": generate_bad_spark_plug_sample,
        "oil_problem": generate_oil_problem_sample,
        "esc_fault": generate_esc_fault_sample
    }

    print(f"Generating {TOTAL_SAMPLES} samples per scenario ({DURATION_MINUTES} minutes at {SAMPLE_INTERVAL_MS}ms intervals)")
    print()

    for name in ["normal_commute", "bad_spark_plug", "oil_problem", "esc_fault"]:
        generate_scenario(name, generators[name], vehicles[name], dtcs[name])

    print()
    print("All sample files generated successfully!")

if __name__ == "__main__":
    main()
