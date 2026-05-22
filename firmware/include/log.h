#pragma once
#include <esp_log.h>
#include "../src/log_emit.h"  // emit_log declared in src/

#define LOGI(tag, fmt, ...) do { ESP_LOGI(tag, fmt, ##__VA_ARGS__); emit_log("info", tag, fmt, ##__VA_ARGS__); } while (0)
#define LOGW(tag, fmt, ...) do { ESP_LOGW(tag, fmt, ##__VA_ARGS__); emit_log("warn", tag, fmt, ##__VA_ARGS__); } while (0)
#define LOGE(tag, fmt, ...) do { ESP_LOGE(tag, fmt, ##__VA_ARGS__); emit_log("err",  tag, fmt, ##__VA_ARGS__); } while (0)
