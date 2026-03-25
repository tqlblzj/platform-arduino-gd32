# Copyright 2024-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Arduino Framework for GD32 Wireless (GD32VW55x)

Arduino Wiring-based Framework allows writing cross-platform software to
control devices attached to a wide range of Arduino boards to create all
kinds of creative coding, interactive objects, spaces or physical experiences.

https://www.gigadevice.com/
"""

import os
import sys
import glob
import re
import subprocess
import tempfile
import shutil
from os import listdir
from os.path import join, isfile, isdir

from SCons.Script import DefaultEnvironment, SConscript

env = DefaultEnvironment()
board = env.BoardConfig()
platform = env.PioPlatform()

# ============================================================================
# Framework and SDK Configuration
# ============================================================================

FRAMEWORK_DIR = platform.get_package_dir("framework-arduino-gd32w")
assert isdir(FRAMEWORK_DIR), "Arduino framework directory not found!"

# Board configuration
build_core = board.get("build.core", "")
build_variant = board.get("build.variant", "")
build_mcu = board.get("build.mcu", "")
build_series = board.get("build.series", "")
build_product_line = board.get("build.product_line", "")

# RISC-V architecture and ABI settings
build_mabi = board.get("build.mabi", "ilp32f").lower().strip()
build_march = board.get("build.march", "rv32imafcbp").lower().strip()
build_mcmodel = board.get("build.mcmodel", "medlow").lower().strip()

# SDK version (can be overridden in platformio.ini)
build_sdk_version = board.get("build.sdk_version", "")

# SDK directory
sdk_mcu = build_series.lower() if build_series else build_mcu
SDK_DIR = join(FRAMEWORK_DIR, "tools", "gd32w-arduino-libs", build_sdk_version, sdk_mcu)

# ============================================================================
# Read SDK Flags from Files
# ============================================================================

SDK_FLAGS_DIR = join(SDK_DIR, "flags")

def read_sdk_flag(filename):
    """Read a single SDK flag file."""
    filepath = join(SDK_FLAGS_DIR, filename)
    if isfile(filepath):
        with open(filepath, 'r') as f:
            return f.read().strip()
    return ""

sdk_cpp_flags = read_sdk_flag("cpp_flags")
sdk_defines = read_sdk_flag("defines")
sdk_includes = read_sdk_flag("includes")
sdk_ld_flags = read_sdk_flag("ld_flags")
sdk_ld_libs = read_sdk_flag("ld_libs")

# ============================================================================
# Import Base Framework
# ============================================================================

SConscript("_bare.py", exports="env")

# ============================================================================
# Parse and Filter Compiler Flags
# ============================================================================

# Parse SDK cpp_flags into a list
sdk_cpp_flags_list = sdk_cpp_flags.split() if sdk_cpp_flags else []

# Handle optimization level
build_optimize = board.get("build.optimization", "")
if build_optimize:
    sdk_cpp_flags_list = [f for f in sdk_cpp_flags_list if not f.startswith("-O")]
    sdk_cpp_flags_list.append(build_optimize)
else:
    sdk_cpp_flags_list = [f for f in sdk_cpp_flags_list if not f.startswith("-O")]
    sdk_cpp_flags_list.append("-Og")

# Add -iprefix for SDK includes
sdk_include_dir = join(SDK_DIR, "include")
if isdir(sdk_include_dir):
    sdk_cpp_flags_list.extend(["-iprefix", sdk_include_dir])

# Parse SDK ld_flags into a list
sdk_ld_flags_list = sdk_ld_flags.split() if sdk_ld_flags else []

# Handle optimization level in linker flags
if build_optimize:
    sdk_ld_flags_list = [f for f in sdk_ld_flags_list if not f.startswith("-O")]
    sdk_ld_flags_list.append(build_optimize)
else:
    sdk_ld_flags_list = [f for f in sdk_ld_flags_list if not f.startswith("-O")]
    sdk_ld_flags_list.append("-Og")

# Separate C++-specific flags from common flags
cxx_only_flags = ["-std=gnu++17", "-fno-rtti", "-fno-exceptions", "-fno-use-cxa-atexit", "-fpermissive", "-Wno-register"]
c_cpp_flags = [f for f in sdk_cpp_flags_list if f not in cxx_only_flags]
cxx_specific_flags = [f for f in sdk_cpp_flags_list if f in cxx_only_flags]

# Flags already in _bare.py (should not be added again)
bare_py_flags = {
    "-ffunction-sections", "-fdata-sections", "-fno-common", "-fsigned-char",
    "-fmessage-length=0", "-msave-restore", "-msmall-data-limit=8", "-nostartfiles",
    "-Xlinker", "--gc-sections", "--specs=nano.specs", "--specs=nosys.specs", "-g"
}

# Filter out duplicate flags
filtered_ld_flags = [f for f in sdk_ld_flags_list if f not in bare_py_flags]

# Filter out architecture flags (already added separately)
arch_flags = {"-march", "-mabi", "-mcmodel", "-msmall-data-limit", "-mno-save-restore"}
filtered_cpp_flags = [f for f in c_cpp_flags if not any(f.startswith(flag) for flag in arch_flags)]

# Filter out flags already in _bare.py
bare_py_flags_simple = {
    "-ffunction-sections", "-fdata-sections", "-fno-common", "-fsigned-char",
    "-fmessage-length=0", "-msave-restore", "-msmall-data-limit=8", "-g"
}
filtered_cpp_flags = [f for f in filtered_cpp_flags if f not in bare_py_flags_simple]

# ============================================================================
# Append Compiler and Linker Flags
# ============================================================================

# Warning suppression flags
warning_suppress_flags = [
    "-w",  # Disable all warnings
]

env.Append(
    CCFLAGS=["-march=%s" % build_march, "-mabi=%s" % build_mabi, "-mcmodel=%s" % build_mcmodel] + filtered_cpp_flags + warning_suppress_flags,
    CXXFLAGS=["-march=%s" % build_march, "-mabi=%s" % build_mabi, "-mcmodel=%s" % build_mcmodel] + filtered_cpp_flags + cxx_specific_flags + warning_suppress_flags,
    ASFLAGS=["-march=%s" % build_march, "-mabi=%s" % build_mabi, "-mcmodel=%s" % build_mcmodel],
    LINKFLAGS=["-march=%s" % build_march, "-mabi=%s" % build_mabi, "-mcmodel=%s" % build_mcmodel] + filtered_ld_flags,
)

# ============================================================================
# Add SDK Defines
# ============================================================================

if sdk_defines:
    sdk_defines_list = sdk_defines.split()
    env.Append(CPPDEFINES=sdk_defines_list)

# ============================================================================
# Arduino Framework Configuration
# ============================================================================

# Core and variant directories
CORE_DIR = join(FRAMEWORK_DIR, "cores", build_core)
VARIANT_DIR = join(FRAMEWORK_DIR, "variants", build_variant)

# ============================================================================
# Build Include Paths
# ============================================================================

CPPPATH = [
    join(CORE_DIR),                    # Arduino core
    join(CORE_DIR, "avr"),             # AVR compatibility
    join(CORE_DIR, "gd32"),            # GD32 specific
    join(VARIANT_DIR),                 # Board variant
]

# Add SDK include paths
if isdir(SDK_DIR):
    sdk_include = join(SDK_DIR, "include")
    sdk_flags = join(SDK_DIR, "flags")
    if isdir(sdk_include):
        CPPPATH.append(sdk_include)
    if isdir(sdk_flags) and sdk_includes:
        # Process -iwithprefixbefore and -I flags
        parts = re.split(r'(\s-iwithprefixbefore\s+|\s-I)', sdk_includes)
        current_flag = None
        for part in parts:
            if part.strip() in (' -iwithprefixbefore ', ' -iwithprefixbefore', '-iwithprefixbefore ', '-iwithprefixbefore'):
                current_flag = '-iwithprefixbefore'
            elif part.strip().startswith('-I'):
                current_flag = '-I'
                flag_text = part.strip()
                inc_path = flag_text[2:].strip()
                if not os.path.isabs(inc_path):
                    inc_path = join(SDK_DIR, "include", inc_path)
                CPPPATH.append(inc_path)
            elif current_flag == '-iwithprefixbefore' and part.strip():
                inc_path = part.strip()
                if not os.path.isabs(inc_path):
                    inc_path = join(SDK_DIR, "include", inc_path)
                CPPPATH.append(inc_path)
                current_flag = None

env.Append(CPPPATH=CPPPATH)

# ============================================================================
# Arduino Standard Libraries
# ============================================================================

LIBRARIES_DIR = join(FRAMEWORK_DIR, "libraries")
if isdir(LIBRARIES_DIR):
    env.Append(
        LIBSOURCE_DIRS=LIBRARIES_DIR,
        LIB_IGNORE_PATTERN="+<example*>",
    )
    # Add library source directories to include path
    for lib_dir in listdir(LIBRARIES_DIR):
        lib_src_dir = join(LIBRARIES_DIR, lib_dir, "src")
        if isdir(lib_src_dir):
            env.Append(CPPPATH=[lib_src_dir])

# ============================================================================
# Build Defines
# ============================================================================

CPPDEFINES = [
    "ARDUINO=10810",                    # Arduino API version
    f"ARDUINO_{board.get('build.board')}",  # Board define
    "ARDUINO_ARCH_RISCV",               # Architecture
    f"{build_series}",                  # Series
    f"{build_product_line}",            # Product line
    'BOARD_NAME="%s"' % board.get("build.board"),
    "SSIZE_MAX=LONG_MAX",               # Fix ssize_t conflict with toolchain
]

env.Append(CPPDEFINES=CPPDEFINES)

# ============================================================================
# Build Core and Variant Libraries
# ============================================================================

# Build core library
core_lib = env.BuildLibrary(
    join("$BUILD_DIR", "framework-arduino-gd32w", "cores"),
    CORE_DIR,
    src_filter=" ".join([
        "+<*.c>",
        "+<*.cpp>",
        "+<gd32/*.c>",
        "+<gd32/*.cpp>",
        "+<avr/*.c>",
        "+<avr/*.cpp>"
    ])
)

libs = [core_lib]

# Build variant library
if isdir(VARIANT_DIR):
    variant_lib = env.BuildLibrary(
        join("$BUILD_DIR", "framework-arduino-gd32w", "variants"),
        VARIANT_DIR,
        src_filter="+<*.c> +<*.cpp>"
    )
    libs.append(variant_lib)

env.Prepend(LIBS=libs)

# ============================================================================
# Linker Script
# ============================================================================

ldscript = board.get("build.ldscript", "")
if not ldscript:
    if isdir(SDK_DIR):
        ld_script_dir = join(SDK_DIR, "ld")
        if isdir(ld_script_dir):
            ld_scripts = glob.glob(join(ld_script_dir, "*.ld"))
            if ld_scripts:
                ldscript = ld_scripts[0]

if ldscript:
    env.Replace(LDSCRIPT_PATH=ldscript)

# ============================================================================
# SDK Libraries
# ============================================================================

if isdir(SDK_DIR):
    sdk_lib_dir = join(SDK_DIR, "lib")
    if isdir(sdk_lib_dir):
        # Add library search path
        env.Append(LIBPATH=sdk_lib_dir)

        # Add SDK libraries to _LIBFLAGS to preserve order
        if sdk_ld_libs:
            current_libflags = env.get('_LIBFLAGS', '')
            if current_libflags:
                env['_LIBFLAGS'] = current_libflags + ' ' + sdk_ld_libs
            else:
                env['_LIBFLAGS'] = sdk_ld_libs

