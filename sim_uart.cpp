#include "sim_uart.h"

UART::UART(uint8_t *tx_valid, uint8_t *tx_ready, uint8_t *tx_data, uint8_t *rx_valid, uint8_t *rx_ready, uint8_t *rx_data) :
    tx_valid(tx_valid),
    tx_ready(tx_ready),
    tx_data(tx_data),
    rx_valid(rx_valid),
    rx_ready(rx_ready),
    rx_data(rx_data)
{}

void UART::tick() {
    *tx_ready = 1;
    if (*tx_valid)
        rx_q.push(*tx_data);

    *rx_valid = 0;
    if (*rx_ready && !tx_q.empty()) {
        *rx_valid = 1;
        *rx_data = tx_q.front();
        tx_q.pop();
    }
}

void UART::write(uint8_t c) {
    tx_q.push(c);
}

void UART::write(std::string str) {
    for (auto c : str)
        this->write(c);
}

std::string UART::read() {
    std::string res;
    res.reserve(rx_q.size());
    while (!rx_q.empty()) {
        res.push_back(rx_q.front());
        rx_q.pop();
    }
    return res;
}

