/*
 * Copyright 2023 Antmicro
 * SPDX-License-Identifier: Apache-2.0
 */

__flash = 0x00000000;
__flash_size = 40K;
__ram = 0x10000000;
__ram_size = 4K;
__stack_size = 1K;

INCLUDE picolibc.ld
