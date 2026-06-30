#ifndef GW_DB_CONN_H
#define GW_DB_CONN_H

// Build a libpq/libpqxx connection string from the standard GeneWeaver
// DB_* environment variables (the same ones the tools-worker receives from
// the `geneweaver-db` secret: DB_HOST, DB_NAME, DB_USERNAME, DB_PASSWORD,
// and optionally DB_PORT). Falls back to the historical localhost/odeadmin
// values when a variable is unset, so a bare local run still behaves as before.
//
// NOTE: uses `host=` (not `hostaddr=`) so DB_HOST may be a hostname or an IP.

#include <cstdlib>
#include <string>

inline std::string gw_conn_string() {
    auto env_or = [](const char* key, const char* fallback) -> std::string {
        const char* v = std::getenv(key);
        return std::string((v && *v) ? v : fallback);
    };

    const std::string host = env_or("DB_HOST", "127.0.0.1");
    const std::string port = env_or("DB_PORT", "5432");
    const std::string name = env_or("DB_NAME", "geneweaver");
    const std::string user = env_or("DB_USERNAME", "odeadmin");
    const std::string pass = env_or("DB_PASSWORD", "odeadmin");

    return "dbname=" + name + " user=" + user + " password=" + pass +
           " host=" + host + " port=" + port;
}

#endif  // GW_DB_CONN_H
