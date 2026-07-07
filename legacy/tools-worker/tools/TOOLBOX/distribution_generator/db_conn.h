#ifndef GW_DB_CONN_H
#define GW_DB_CONN_H

// Shared env-driven config for the TOOLBOX distribution_generator tools:
//   * gw_conn_string()   — libpq/libpqxx connection string from DB_* env vars
//   * gw_dist_data_dir() — directory for the genes.dat / homology.dat caches
//   * gw_mkdir_p()       — recursive mkdir (so the data dir can be created)
//
// All fall back to historical defaults when the env vars are unset, so a bare
// local run still behaves sensibly.

#include <cstdlib>
#include <string>
#include <sys/stat.h>
#include <sys/types.h>
#include <errno.h>

inline std::string gw_env_or(const char* key, const char* fallback) {
    const char* v = std::getenv(key);
    return std::string((v && *v) ? v : fallback);
}

// Connection string built from DB_HOST/DB_PORT/DB_NAME/DB_USERNAME/DB_PASSWORD
// (the geneweaver-db secret env). Uses host= so DB_HOST may be a name or an IP.
inline std::string gw_conn_string() {
    const std::string host = gw_env_or("DB_HOST", "127.0.0.1");
    const std::string port = gw_env_or("DB_PORT", "5432");
    const std::string name = gw_env_or("DB_NAME", "geneweaver");
    const std::string user = gw_env_or("DB_USERNAME", "odeadmin");
    const std::string pass = gw_env_or("DB_PASSWORD", "odeadmin");
    return "dbname=" + name + " user=" + user + " password=" + pass +
           " host=" + host + " port=" + port;
}

// Directory holding the regenerable genes.dat / homology.dat sampling caches.
// Prefer GW_DIST_DATA_DIR; otherwise place it under APPLICATION_RESULTS (the
// shared results PVC the worker already mounts); else a sane default.
inline std::string gw_dist_data_dir() {
    const char* d = std::getenv("GW_DIST_DATA_DIR");
    if (d && *d) return std::string(d);
    const char* r = std::getenv("APPLICATION_RESULTS");
    if (r && *r) return std::string(r) + "/dist_data";
    return "/var/geneweaver/results/dist_data";
}

// Recursive mkdir (like `mkdir -p`). Returns 0 on success or if it exists.
inline int gw_mkdir_p(const std::string& path, mode_t mode = 0775) {
    std::string acc;
    for (size_t i = 0; i < path.size(); ++i) {
        acc += path[i];
        if (path[i] == '/' || i + 1 == path.size()) {
            if (acc == "/" ) continue;
            if (mkdir(acc.c_str(), mode) != 0 && errno != EEXIST) return -1;
        }
    }
    return 0;
}

#endif  // GW_DB_CONN_H
