// Copyright 2023 Antmicro
// SPDX-License-Identifier: Apache-2.0

#include <memory>

#include <stdlib.h>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>

#include <verilated.h>

#include "Vtop.h"
#include "verilated_vcd_c.h"
#include "sim_uart.h"

#define PERROR_EXIT(msg) \
    do { \
        perror(msg); \
        exit(EXIT_FAILURE); \
    } while(0)

int main(int argc, char** argv) {
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->debug(0);
    contextp->randReset(2);
    contextp->traceEverOn(true);
    contextp->commandArgs(argc, argv);

    const std::unique_ptr<Vtop> soc{new Vtop{contextp.get(), "top"}};
    VerilatedVcdC* tfp = new VerilatedVcdC;
    soc->trace(tfp, 99);
    tfp->open("dump.vcd");

    // Open PTY
    int pty_fd;
    if ((pty_fd = posix_openpt(O_RDWR | O_NOCTTY)) < 0)
        PERROR_EXIT("Opening pseudoterminal failed");
    if (grantpt(pty_fd) < 0)
        PERROR_EXIT("grantpt failed");
    if (unlockpt(pty_fd) < 0)
        PERROR_EXIT("unlockpt failed");

    // set master pty to nonblocking
    int status_f;
    if ((status_f = fcntl(pty_fd, F_GETFL)) < 0)
        PERROR_EXIT("Getting file status flags on pseudoterminal failed");
    if (fcntl(pty_fd, F_SETFL, status_f | O_NONBLOCK) < 0)
        PERROR_EXIT("Getting file status flags on pseudoterminal failed");

    // turn off echo
    struct termios termopts;
    if (tcgetattr(pty_fd, &termopts) < 0)
        PERROR_EXIT("Getting terminal options failed");
    termopts.c_lflag &= ~ECHO;
    if (tcsetattr(pty_fd, TCSADRAIN, &termopts) < 0)
        PERROR_EXIT("Setting terminal options failed");

    char *pty_name = ptsname(pty_fd);
    if (pty_name)
        std::cout<<"Terminal opened at "<<pty_name<<std::endl;

    UART uart(
        &soc->sim_serial_source_valid,
        &soc->sim_serial_source_ready,
        &soc->sim_serial_source_data,
        &soc->sim_serial_sink_valid,
        &soc->sim_serial_sink_ready,
        &soc->sim_serial_sink_data
    );

    soc->clk100 = 0;
    while (contextp->time() < 100000) {
        contextp->timeInc(1);
	soc->clk100 = !soc->clk100;

        if (!soc->clk100) {
            uart.tick();
        }

        soc->eval();
        tfp->dump(contextp->time());

        uint8_t c;
        if (read(pty_fd, &c, 1) > 0)
            uart.write(c);
        std::string to_write = uart.read();
        write(pty_fd, to_write.c_str(), to_write.size());

        // Read outputs
        if ((soc->sim_serial_source_valid || soc->sim_serial_sink_valid) && contextp->time() % 2 == 0)
            VL_PRINTF("[%" PRId64 "] TX: 0x%x RX: 0x%x\n", contextp->time()/2,
                soc->sim_serial_source_valid ? soc->sim_serial_source_data : 0,    // data comes out of sources
                soc->sim_serial_sink_valid ? soc->sim_serial_sink_data : 0         // data goes into sinks
            );
    }

    soc->final();
    tfp->close();
    close(pty_fd);
    return 0;
}
