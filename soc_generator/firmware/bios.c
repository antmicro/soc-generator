/*
 * Copyright 2023 Antmicro
 * SPDX-License-Identifier: Apache-2.0
 */

#include "uart_stdio.h"

int main(int argc, char **argv) {
	uart_stdio_init();
	printf("hello world");
}
