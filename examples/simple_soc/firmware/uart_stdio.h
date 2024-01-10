/*
 * Copyright 2023 Antmicro
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef H_UART_STDIO
#define H_UART_STDIO

#include <stdio.h>
#include <uart.h>

extern FILE *const stdout;
extern FILE *const stderr;
extern FILE *const stdin;

int uart_putc(char c, FILE *file);
int uart_getc(FILE *file);
void uart_stdio_init();

#endif

