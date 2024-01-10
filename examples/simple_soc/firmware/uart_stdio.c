/*
 * Copyright 2023 Antmicro
 * SPDX-License-Identifier: Apache-2.0
 */

#include "uart_stdio.h"

static FILE __stdio = FDEV_SETUP_STREAM(uart_putc, uart_getc, NULL, _FDEV_SETUP_RW);

FILE *const stdout = &__stdio;
FILE *const stderr = &__stdio;
FILE *const stdin  = &__stdio;

int uart_putc(char c, FILE *file) {
	(void)file;
	uart_write(c);
	if (c == '\n')
		uart_write('\r');
	return c;
}

int uart_getc(FILE *file) {
	(void)file;
	return uart_read();
}

void uart_stdio_init() {
	uart_init();
}

