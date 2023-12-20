// DESCRIPTION: Verilator: Verilog example module
//
// This file ONLY is placed under the Creative Commons Public Domain, for
// any use, without warranty, 2017 by Wilson Snyder.
// SPDX-License-Identifier: CC0-1.0
//======================================================================

// For std::unique_ptr
#include <memory>

// Include common routines
#include <verilated.h>

#include <stdlib.h>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>

// Include model header, generated from Verilating "soc.v"
#include "Vtop.h"

#include "verilated_vcd_c.h"

#include "sim_uart.h"

#define PERROR_EXIT(msg) \
    do { \
        perror(msg); \
        exit(EXIT_FAILURE); \
    } while(0)

// Legacy function required only so linking works on Cygwin and MSVC++
double sc_time_stamp() { return 0; }

int main(int argc, char** argv) {
    // This is a more complicated example, please also see the simpler examples/make_hello_c.

    // Prevent unused variable warnings
    if (false && argc && argv) {}

    // Create logs/ directory in case we have traces to put under it
    Verilated::mkdir("logs");

    // Construct a VerilatedContext to hold simulation time, etc.
    // Multiple modules (made later below with Vtop) may share the same
    // context to share time, or modules may have different contexts if
    // they should be independent from each other.

    // Using unique_ptr is similar to
    // "VerilatedContext* contextp = new VerilatedContext" then deleting at end.
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    // Do not instead make Vtop as a file-scope static variable, as the
    // "C++ static initialization order fiasco" may cause a crash

    // Set debug level, 0 is off, 9 is highest presently used
    // May be overridden by commandArgs argument parsing
    contextp->debug(0);

    // Randomization reset policy
    // May be overridden by commandArgs argument parsing
    contextp->randReset(2);

    // Verilator must compute traced signals
    contextp->traceEverOn(true);

    // Pass arguments so Verilated code can see them, e.g. $value$plusargs
    // This needs to be called before you create any model
    contextp->commandArgs(argc, argv);

    // Construct the Verilated model, from Vtop.h generated from Verilating "soc.v".
    // Using unique_ptr is similar to "Vtop* soc = new Vtop" then deleting at end.
    // "soc" will be the hierarchical name of the module.
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

    // Set Vtop's input signals
    soc->clk100 = 0;

    while (contextp->time() < 100000) {
        // Historical note, before Verilator 4.200 Verilated::gotFinish()
        // was used above in place of contextp->gotFinish().
        // Most of the contextp-> calls can use Verilated:: calls instead;
        // the Verilated:: versions just assume there's a single context
        // being used (per thread).  It's faster and clearer to use the
        // newer contextp-> versions.

        contextp->timeInc(1);  // 1 timeprecision period passes...
        // Historical note, before Verilator 4.200 a sc_time_stamp()
        // function was required instead of using timeInc.  Once timeInc()
        // is called (with non-zero), the Verilated libraries assume the
        // new API, and sc_time_stamp() will no longer work.

        // Toggle a fast (time/2 period) clock
        soc->clk100 = !soc->clk100;

        // Toggle control signals on an edge that doesn't correspond
        // to where the controls are sampled; in this example we do
        // this only on a negedge of clk100, because we know
        // reset is not sampled there.
        if (!soc->clk100) {
            uart.tick();
        }

        // Evaluate model
        // (If you have multiple models being simulated in the same
        // timestep then instead of eval(), call eval_step() on each, then
        // eval_end_step() on each. See the manual.)
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

    // Final model cleanup
    soc->final();
    tfp->close();

    // Coverage analysis (calling write only after the test is known to pass)
#if VM_COVERAGE
    Verilated::mkdir("logs");
    contextp->coveragep()->write("logs/coverage.dat");
#endif

    close(pty_fd);
    // Return good completion status
    // Don't use exit() or destructor won't get called
    return 0;
}
