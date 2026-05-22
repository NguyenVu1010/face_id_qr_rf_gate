#pragma once
#include <stddef.h>

void   allowlist_init();
bool   allowlist_lookup(const char* uid_hex, char* name_out, size_t name_out_n);
int    allowlist_add(const char* uid_hex, const char* name);   // returns new total, or -1 if full / -2 on NVS error
bool   allowlist_remove(const char* uid_hex);                  // false if not found
size_t allowlist_list_json(char* out_json, size_t out_json_n); // writes [{"uid":"...","name":"..."},...]; returns bytes written or 0 on overflow
size_t allowlist_count();
