# Copyright 2014-present PlatformIO <contact@platformio.org>
# Copyright 2019-present Nuclei <contact@nucleisys.com>
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

import sys
import os
import subprocess
from platform import system
from os import makedirs
from os.path import join, isfile, isdir

from SCons.Script import (ARGUMENTS, COMMAND_LINE_TARGETS, AlwaysBuild,
                          Builder, Default, DefaultEnvironment)

env = DefaultEnvironment()
platform = env.PioPlatform()
board_config = env.BoardConfig()

# ============================================================================
# Toolchain Configuration
# ============================================================================

framework_dir = platform.get_package_dir("framework-arduino-gd32w")
framework_toolchain_dir = None

# Get toolchain version from board config
build_toolchain_version = board_config.get("build.toolchain_version", "1.0.0")

if framework_dir:
    # Check for Windows toolchain
    tc_path = join(framework_dir, "tools", "gd32vw553_toolchain_windows", build_toolchain_version)
    if isdir(tc_path):
        framework_toolchain_dir = tc_path

tc_bin_dir = join(framework_toolchain_dir, "bin") if framework_toolchain_dir else None
exe_suffix = ".exe" if system() == "Windows" else ""

if framework_toolchain_dir and tc_bin_dir and isdir(tc_bin_dir):
    # Use framework's toolchain
    env.Replace(
        AR=join(tc_bin_dir, "riscv-nuclei-elf-gcc-ar" + exe_suffix),
        AS=join(tc_bin_dir, "riscv-nuclei-elf-as" + exe_suffix),
        CC=join(tc_bin_dir, "riscv-nuclei-elf-gcc" + exe_suffix),
        GDB=join(tc_bin_dir, "riscv-nuclei-elf-gdb" + exe_suffix),
        CXX=join(tc_bin_dir, "riscv-nuclei-elf-g++" + exe_suffix),
        OBJCOPY=join(tc_bin_dir, "riscv-nuclei-elf-objcopy" + exe_suffix),
        RANLIB=join(tc_bin_dir, "riscv-nuclei-elf-gcc-ranlib" + exe_suffix),
        SIZETOOL=join(tc_bin_dir, "riscv-nuclei-elf-size" + exe_suffix),
        ARFLAGS=["rc"],
        SIZEPRINTCMD='$SIZETOOL -d $SOURCES',
        PROGSUFFIX=".elf"
    )
else:
    # Use default toolchain
    env.Replace(
        AR="riscv-nuclei-elf-gcc-ar",
        AS="riscv-nuclei-elf-as",
        CC="riscv-nuclei-elf-gcc",
        GDB="riscv-nuclei-elf-gdb",
        CXX="riscv-nuclei-elf-g++",
        OBJCOPY="riscv-nuclei-elf-objcopy",
        RANLIB="riscv-nuclei-elf-gcc-ranlib",
        SIZETOOL="riscv-nuclei-elf-size",
        ARFLAGS=["rc"],
        SIZEPRINTCMD='$SIZETOOL -d $SOURCES',
        PROGSUFFIX=".elf"
    )

# ============================================================================
# Framework Selection
# ============================================================================

if not env.get("PIOFRAMEWORK"):
    env.SConscript("frameworks/_bare.py", exports="env")

# ============================================================================
# Build Targets
# ============================================================================

# Target: Build executable and linkable firmware
target_elf = None
if "nobuild" in COMMAND_LINE_TARGETS:
    target_elf = join("$BUILD_DIR", "${PROGNAME}.elf")
    target_bin = join("$BUILD_DIR", "${PROGNAME}.bin")
else:
    target_elf = env.BuildProgram()

AlwaysBuild(env.Alias("nobuild", target_elf))
target_buildprog = env.Alias("buildprog", target_elf, target_elf)

# ============================================================================
# ELF to BIN Conversion
# ============================================================================

def _convert_elf_to_bin(target, source, env):
    """Convert ELF file to BIN format."""
    elf_file = env.subst(join("$BUILD_DIR", "${PROGNAME}.elf"))
    bin_file = env.subst(join("$BUILD_DIR", "${PROGNAME}.bin"))

    print(f"Converting {elf_file} to {bin_file}")

    if not os.path.exists(elf_file):
        print(f"ERROR: ELF file not found: {elf_file}")
        return 1

    # Check ELF file sections
    size_cmd = [env.subst("$SIZETOOL"), "-A", elf_file]
    size_result = subprocess.run(size_cmd, capture_output=True, text=True)

    # Convert to binary
    objcopy_cmd = [env.subst("$OBJCOPY"), "-O", "binary", elf_file, bin_file]

    result = subprocess.run(objcopy_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"objcopy error (code {result.returncode}):")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        return result.returncode

    if os.path.exists(bin_file):
        size = os.path.getsize(bin_file)
        print(f"Generated BIN: {bin_file} (size: {size} bytes)")
    else:
        print(f"ERROR: BIN file not created: {bin_file}")
        return 1

    return 0

# Add post-action to the buildprog alias
env.AddPostAction(target_buildprog, env.VerboseAction(_convert_elf_to_bin, "Converting ELF to BIN"))

# ============================================================================
# Size Target
# ============================================================================

target_size = env.Alias(
    "size", target_elf,
    env.VerboseAction("$SIZEPRINTCMD", "Calculating size $SOURCE"))
AlwaysBuild(target_size)

# ============================================================================
# Upload Configuration
# ============================================================================

upload_protocol = "gdlink"
upload_actions = []
upload_target = target_elf

# Get upload tools directory
upload_tools_dir = None
if framework_dir:
    # Get upload tools version from board config (default: 1.0.0)
    build_upload_tools_version = board_config.get("build.upload_tools_version", "1.0.0")
    upload_tools_path = join(framework_dir, "tools", "gd32w-upload-tools", build_upload_tools_version, "win")
    if isdir(upload_tools_path):
        upload_tools_dir = upload_tools_path

# ============================================================================
# Firmware Combination with MBL Bootloader
# ============================================================================

def _combine_firmware_with_mbl(env, openocd_dir, source_bin):
    """Combine MBL bootloader with firmware binary."""
    build_dir = env.subst("$BUILD_DIR")
    print("build_dir: %s" % build_dir)

    # Get paths - mbl.bin is in OpenOCD_2022.4.6 subdirectory
    mbl_bin = join(openocd_dir, "OpenOCD_2022.4.6", "mbl.bin")
    combined_bin = join(build_dir, "combined_firmware.bin")

    # Read MBL and firmware data
    with open(mbl_bin, 'rb') as f:
        mbl_data = f.read()

    with open(source_bin, 'rb') as f:
        firmware_data = f.read()

    # MBL size is 0xA000 (40KB)
    mbl_size = 0xA000

    # Create combined firmware
    with open(combined_bin, 'wb') as f:
        # Write MBL
        f.write(mbl_data)

        # Pad with 0xFF if needed
        pad_needed = mbl_size - len(mbl_data)
        if pad_needed > 0:
            f.write(b'\xFF' * pad_needed)

        # Write firmware
        f.write(firmware_data)

    print("Combined firmware created: %s" % combined_bin)
    return combined_bin

# ============================================================================
# Upload Actions
# ============================================================================

def _openocd_upload(env, source, target=None):
    """Upload firmware using OpenOCD."""
    import subprocess

    # Convert ELF to BIN if needed
    source_file = str(source[0]) if source else ""
    if source_file.endswith('.elf'):
        bin_file = source_file.replace('.elf', '.bin')
        objcopy = env.subst("$OBJCOPY")
        subprocess.run([objcopy, "-O", "binary", source_file, bin_file], check=True)
        source_file = bin_file

    # Combine firmware with MBL bootloader
    combined_bin = _combine_firmware_with_mbl(env, upload_tools_dir, source_file)

    # Convert to forward slashes for OpenOCD
    combined_bin_slash = combined_bin.replace('\\', '/')

    # Get OpenOCD config file
    if upload_protocol == "jlink":
        openocd_cfg = join(upload_tools_dir, "OpenOCD_2022.4.6", "openocd_jlink.cfg")
    else:  # gdlink
        openocd_cfg = join(upload_tools_dir, "OpenOCD_2022.4.6", "openocd_gdlink.cfg")

    openocd_exe = join(upload_tools_dir, "OpenOCD_2022.4.6", "openocd.exe")

    # Run OpenOCD
    cmd = [
        openocd_exe,
        "-f", openocd_cfg,
        "-c", "program %s 0x08000000 verify reset exit;" % combined_bin_slash
    ]

    print("Running: %s" % " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        sys.stderr.write("OpenOCD error:\n%s\n" % result.stderr.decode())
        return result.returncode

    print("Upload completed successfully!")
    return 0

# Configure upload based on protocol
if upload_protocol in ("jlink", "gdlink"):
    if not upload_tools_dir:
        sys.stderr.write("Error: Upload tools directory not found!\n")
    else:
        upload_target = target_elf
        upload_actions = [env.VerboseAction(_openocd_upload, "Uploading $SOURCE")]
else:
    sys.stderr.write("Warning! Unknown upload protocol %s\n" % upload_protocol)

AlwaysBuild(env.Alias("upload", upload_target, upload_actions))

# ============================================================================
# Default Targets
# ============================================================================

Default([target_buildprog, target_size])
