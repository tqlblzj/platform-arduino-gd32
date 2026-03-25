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

#
# Default flags for bare-metal programming (without any framework layers)
#

from SCons.Script import Import

Import("env")

env.Append(
    CCFLAGS=[
        "-Wall",  # show warnings
        "-ffunction-sections",
        "-fdata-sections",
        "-fno-common",
        "-fsigned-char",
        "-fmessage-length=0",
        "-msave-restore",
        "-msmall-data-limit=8",
        "-g"
    ],

    # C-specific flags
    CFLAGS=[
        "-std=c99",
    ],

    # C++-specific flags
    CXXFLAGS=[
        "-std=gnu++17",
    ],

    ASFLAGS=[
        "-fmessage-length=0",
        "-fsigned-char",
        "-msave-restore",
        "-fno-common",
        "-fdata-sections",
        "-ffunction-sections",
        "-msmall-data-limit=8",
        "-x"
        "assembler-with-cpp",
        "-Wuninitialized",
        "-g"
    ],

    LINKFLAGS=[
        "-ffunction-sections",
        "-msave-restore",
        "-msmall-data-limit=8",
        "-fmessage-length=0",
        "-fdata-sections",
        "-nostartfiles",
        "-fsigned-char",
        "-fno-common",
        "-Xlinker",
        "--gc-sections",
        "--specs=nano.specs",
        "--specs=nosys.specs",
        "-g"
    ],

    LIBS=[],
)