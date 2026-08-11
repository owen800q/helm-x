// platform.h — cross-platform compatibility layer
//
// Bridges the Windows-only pieces of helm-x (WinSock2 sockets, WinHTTP
// client, ShellExecute, GetModuleFileName) to POSIX so the same source
// builds and runs on macOS and Linux. Windows keeps its native code paths;
// this header only supplies the non-Windows equivalents.
#pragma once

#include <string>
#include <utility>
#include <vector>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
// Keep <windows.h> from defining min()/max() macros, which break std::min/max.
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

// WinSock name shims so the shared socket code compiles unchanged.
typedef int SOCKET;
#ifndef INVALID_SOCKET
#define INVALID_SOCKET (-1)
#endif
#ifndef SOCKET_ERROR
#define SOCKET_ERROR (-1)
#endif
inline int closesocket(int fd) { return ::close(fd); }
#endif

namespace helmx {

// Absolute directory of the running executable, with a trailing separator.
// Returns "" if it cannot be resolved.
std::string executable_dir();

// Path to a file that lives next to the executable. Falls back to the bare
// name (current working directory) when the executable dir is unknown.
std::string exe_relative(const std::string& name);

// Open a URL in the system default browser (best effort, non-blocking).
void open_url(const std::string& url);

// Re-launch the current executable with no arguments after the current
// process exits, then terminate this process. Used by the UI "restart"
// action. Does not return on success.
void restart_self();

// ── minimal one-shot HTTP(S) client ──
// TLS is handled by the platform (WinHTTP on Windows, curl elsewhere) so the
// callers stay dependency-free. Blocking; intended for small JSON request/
// response bodies.
struct HttpClientRequest {
    std::string host;
    int port = 443;
    std::string path = "/";
    bool tls = true;
    std::vector<std::pair<std::string, std::string>> headers;
    std::string body;
    std::string user_agent;
    std::string proxy_url;  // optional "http://host:port"; empty = direct
    int timeout_sec = 60;       // absolute ceiling for the whole transfer
    int idle_timeout_sec = 0;   // >0: abort only after this many seconds of
                                // no throughput (a real stall), so a slow but
                                // still-streaming SSE response is not cut off
                                // at a fixed wall while tokens keep arriving.
};

// Performs a POST. On transport success returns true and fills status +
// resp (raw response body). Returns false on transport failure.
bool http_post(const HttpClientRequest& req, int& status, std::string& resp);

}  // namespace helmx
