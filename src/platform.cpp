// platform.cpp — cross-platform helpers (see platform.h)
#include "platform.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

#ifdef _WIN32
#include <windows.h>
#include <shellapi.h>
#else
#include <sys/wait.h>
#include <unistd.h>
#include <cerrno>
#endif

#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif

namespace helmx {

// ── executable path ──
std::string executable_dir() {
    std::string full;
#ifdef _WIN32
    char buf[MAX_PATH] = {0};
    DWORD n = GetModuleFileNameA(nullptr, buf, MAX_PATH);
    if (n > 0 && n < MAX_PATH) full.assign(buf, n);
#elif defined(__APPLE__)
    char buf[4096];
    uint32_t size = sizeof(buf);
    if (_NSGetExecutablePath(buf, &size) == 0) full = buf;
#else  // Linux / other POSIX
    char buf[4096];
    ssize_t n = ::readlink("/proc/self/exe", buf, sizeof(buf) - 1);
    if (n > 0) full.assign(buf, (size_t)n);
#endif
    if (full.empty()) return "";
    size_t slash = full.find_last_of("\\/");
    if (slash == std::string::npos) return "";
    return full.substr(0, slash + 1);  // includes trailing separator
}

std::string exe_relative(const std::string& name) {
    std::string dir = executable_dir();
    if (dir.empty()) return name;
    return dir + name;
}

// ── open URL in default browser ──
void open_url(const std::string& url) {
#ifdef _WIN32
    ShellExecuteA(nullptr, "open", url.c_str(), nullptr, nullptr, SW_SHOWNORMAL);
#else
    // single-quote-escape the URL for the shell
    std::string safe;
    safe.reserve(url.size() + 2);
    for (char c : url) {
        if (c == '\'') safe += "'\\''";
        else safe.push_back(c);
    }
#if defined(__APPLE__)
    std::string cmd = "open '" + safe + "' >/dev/null 2>&1 &";
#else
    std::string cmd = "xdg-open '" + safe + "' >/dev/null 2>&1 &";
#endif
    int rc = std::system(cmd.c_str());
    (void)rc;
#endif
}

#ifndef _WIN32
// ── restart the current process (POSIX) ──
void restart_self() {
    std::string exe;
#if defined(__APPLE__)
    char buf[4096];
    uint32_t size = sizeof(buf);
    if (_NSGetExecutablePath(buf, &size) == 0) exe = buf;
#else
    char buf[4096];
    ssize_t n = ::readlink("/proc/self/exe", buf, sizeof(buf) - 1);
    if (n > 0) exe.assign(buf, (size_t)n);
#endif
    if (exe.empty()) return;

    // Detach a child that waits for us to exit, then re-execs the binary.
    pid_t pid = ::fork();
    if (pid == 0) {
        ::setsid();
        std::string safe;
        for (char c : exe) {
            if (c == '\'') safe += "'\\''";
            else safe.push_back(c);
        }
        std::string cmd = "sleep 1; exec '" + safe + "'";
        ::execl("/bin/sh", "sh", "-c", cmd.c_str(), (char*)nullptr);
        _exit(127);
    }
}

// ── curl-config-file escaping ──
// Within a curl config double-quoted string, backslash escapes the next
// character; escape backslash and double-quote so arbitrary header/URL bytes
// survive intact. No user data ever reaches the shell command line — all of
// it goes through the config file curl reads directly.
static std::string curl_cfg_escape(const std::string& s) {
    std::string out;
    out.reserve(s.size() + 8);
    for (char c : s) {
        switch (c) {
            case '\\': out += "\\\\"; break;
            case '"':  out += "\\\""; break;
            case '\t': out += "\\t"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            default:   out.push_back(c);
        }
    }
    return out;
}

static bool read_whole_file(const std::string& path, std::string& out) {
    FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) return false;
    char buf[8192];
    size_t n;
    while ((n = std::fread(buf, 1, sizeof(buf), f)) > 0) out.append(buf, n);
    std::fclose(f);
    return true;
}

// ── HTTP(S) POST via curl (POSIX) ──
bool http_post(const HttpClientRequest& req, int& status, std::string& resp) {
    status = 0;
    resp.clear();

    char body_tmp[] = "/tmp/helmx_body_XXXXXX";
    char out_tmp[] = "/tmp/helmx_out_XXXXXX";
    char cfg_tmp[] = "/tmp/helmx_cfg_XXXXXX";

    int bf = ::mkstemp(body_tmp);
    if (bf < 0) return false;
    if (!req.body.empty()) {
        ssize_t w = ::write(bf, req.body.data(), req.body.size());
        (void)w;
    }
    ::close(bf);

    int of = ::mkstemp(out_tmp);
    if (of < 0) { ::unlink(body_tmp); return false; }
    ::close(of);

    int cf = ::mkstemp(cfg_tmp);
    if (cf < 0) { ::unlink(body_tmp); ::unlink(out_tmp); return false; }

    std::string scheme = req.tls ? "https" : "http";
    std::string url = scheme + "://" + req.host + ":" + std::to_string(req.port) + req.path;

    std::string cfg;
    cfg += "silent\n";
    cfg += "show-error\n";
    cfg += "request = \"POST\"\n";
    cfg += "url = \"" + curl_cfg_escape(url) + "\"\n";
    cfg += "max-time = \"" + std::to_string(req.timeout_sec > 0 ? req.timeout_sec : 60) + "\"\n";
    if (!req.user_agent.empty())
        cfg += "user-agent = \"" + curl_cfg_escape(req.user_agent) + "\"\n";
    if (!req.proxy_url.empty())
        cfg += "proxy = \"" + curl_cfg_escape(req.proxy_url) + "\"\n";
    for (const auto& h : req.headers)
        cfg += "header = \"" + curl_cfg_escape(h.first + ": " + h.second) + "\"\n";
    cfg += "data-binary = \"@" + std::string(body_tmp) + "\"\n";
    cfg += "output = \"" + std::string(out_tmp) + "\"\n";
    cfg += "write-out = \"%{http_code}\"\n";

    ssize_t cw = ::write(cf, cfg.data(), cfg.size());
    (void)cw;
    ::close(cf);

    // cfg_tmp is a mkstemp path (safe chars only); no request data on the
    // command line, so this is injection-safe.
    std::string cmd = "curl --config '" + std::string(cfg_tmp) + "'";
    FILE* p = ::popen(cmd.c_str(), "r");
    std::string code;
    if (p) {
        char buf[64];
        size_t n;
        while ((n = std::fread(buf, 1, sizeof(buf), p)) > 0) code.append(buf, n);
        ::pclose(p);
    }

    read_whole_file(out_tmp, resp);

    ::unlink(body_tmp);
    ::unlink(out_tmp);
    ::unlink(cfg_tmp);

    if (code.empty()) return false;  // curl missing or transport failure
    status = std::atoi(code.c_str());
    return status > 0;
}
#endif  // !_WIN32

}  // namespace helmx
