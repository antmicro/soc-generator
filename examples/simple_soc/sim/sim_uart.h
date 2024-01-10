/*
 * Copyright 2023 Antmicro
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef H_SIM_UART
#define H_SIM_UART

#include <string>
#include <queue>
#include <cstdint>

class UART {
    private:
        uint8_t *tx_valid;
        uint8_t *tx_ready;
        uint8_t *tx_data;
        uint8_t *rx_valid;
        uint8_t *rx_ready;
        uint8_t *rx_data;
        std::queue<uint8_t> tx_q;
        std::queue<uint8_t> rx_q;
    public:
        UART(uint8_t *tx_valid, uint8_t *tx_ready, uint8_t *tx_data, uint8_t *rx_valid, uint8_t *rx_ready, uint8_t *rx_data);
        void tick();

        void write(uint8_t c);
        void write(std::string str);
        std::string read();
};

#endif
