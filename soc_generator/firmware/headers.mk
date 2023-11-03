# Copyright 2023 Antmicro
# SPDX-License-Identifier: Apache-2.0

HEADERS = csr.h soc.h mem.h
AUTOGEN_H = $(addprefix $(BUILD_DIR)/generated/,$(HEADERS))
