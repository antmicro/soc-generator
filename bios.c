#include "uart_stdio.h"

int main(int argc, char **argv) {
	uart_stdio_init();
	printf("hello world");
}
