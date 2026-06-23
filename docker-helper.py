#!/usr/bin/env python3

import logging
import os
import re
import shlex
import socket
import subprocess as sp
import sys
import time

import scripts.util as util

try:
    import coloredlogs
    coloredlogs.install(level=logging.INFO)
except ImportError:
    logging.basicConfig(level=logging.INFO)


DEFAULT_SERVICES = [
    {"name": "http", "guest_port": 80, "container_port": 10080, "hint": "http://{host}:{port}/"},
    {"name": "https", "guest_port": 443, "container_port": 10443, "hint": "https://{host}:{port}/"},
    {"name": "ssh", "guest_port": 22, "container_port": 10022, "hint": "ssh -p {port} root@{host}"},
    {"name": "telnet", "guest_port": 23, "container_port": 10023, "hint": "telnet {host} {port}"},
    {"name": "http-alt", "guest_port": 8080, "container_port": 18080, "hint": "http://{host}:{port}/"},
    {"name": "https-alt", "guest_port": 8443, "container_port": 18443, "hint": "https://{host}:{port}/"},
    {"name": "debug-nc", "guest_port": 31337, "container_port": 31337, "hint": "nc {host} {port}"},
    {"name": "debug-shell", "guest_port": 31338, "container_port": 31338, "hint": "telnet {host} {port}"},
]

KNOWN_SERVICE_HINTS = {
    22: ("ssh", "ssh -p {port} root@{host}"),
    23: ("telnet", "telnet {host} {port}"),
    80: ("http", "http://{host}:{port}/"),
    443: ("https", "https://{host}:{port}/"),
    8080: ("http-alt", "http://{host}:{port}/"),
    8443: ("https-alt", "https://{host}:{port}/"),
    31337: ("debug-nc", "nc {host} {port}"),
    31338: ("debug-shell", "telnet {host} {port}"),
}


def print_usage(argv0):
    print("Usage: sudo {} [--aslr|--no-aslr] <firmware>".format(argv0))


def check_output(args, **kwargs):
    return sp.check_output(args, stderr=sp.STDOUT, **kwargs)


def safe_container_name(iid, firmware_path):
    filename = os.path.basename(firmware_path)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", filename)[:42].strip("_.-")
    return "firmae_{}_{}_{}".format(iid, safe_name or "firmware", int(time.time()))


def docker_exec(container_name, cmd, detach=False):
    args = ["docker", "exec"]
    if detach:
        args.append("-d")
    args.extend([container_name, "bash", "-lc", cmd])
    return check_output(args)


def docker_path_exists(container_name, path):
    cmd = "test -e {}".format(shlex.quote(path))
    return sp.call(
        ["docker", "exec", container_name, "bash", "-lc", cmd],
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL,
    ) == 0


def docker_process_running(container_name):
    cmd = r"pgrep -af '(\./run\.sh -(r|d)|/scripts/run\.[^ ]+\.sh|qemu-system-)' >/dev/null"
    return sp.call(
        ["docker", "exec", container_name, "bash", "-lc", cmd],
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL,
    ) == 0


def docker_read_file(container_name, path):
    cmd = "cat {}".format(shlex.quote(path))
    return check_output(["docker", "exec", container_name, "bash", "-lc", cmd]).decode().strip()


def docker_file_contains(container_name, path, text):
    cmd = "grep -Fq -- {} {}".format(shlex.quote(text), shlex.quote(path))
    return sp.call(
        ["docker", "exec", container_name, "bash", "-lc", cmd],
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL,
    ) == 0


def docker_run(container_name):
    args = [
        "docker", "run", "-dit", "--rm",
        "--privileged=true",
        "--name", container_name,
    ]
    args.append("fcore")
    check_output(args)


def docker_bridge_ip(container_name):
    output = check_output([
        "docker", "inspect",
        "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
        container_name,
    ]).decode().strip()
    if not output:
        raise RuntimeError("cannot determine docker bridge IP for {}".format(container_name))
    return output


def published_endpoint(publish_container_name, container_port):
    output = check_output(["docker", "port", publish_container_name, "{}/tcp".format(container_port)]).decode()
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return None

    for line in lines:
        if line.startswith("0.0.0.0:") or re.match(r"^[0-9.]+:[0-9]+$", line):
            host, port = line.rsplit(":", 1)
            return host, port

    host, port = lines[0].rsplit(":", 1)
    return host.strip("[]"), port


def wait_for_result(container_name, iid, timeout=2400):
    result_path = "/work/FirmAE/scratch/{}/result".format(iid)
    log_path = "/work/FirmAE/scratch/{}/makeNetwork.log".format(iid)
    started = time.time()
    next_update = started

    while time.time() - started < timeout:
        if docker_path_exists(container_name, result_path):
            result = docker_read_file(container_name, result_path)
            return result == "true"

        if time.time() - started > 10 and not docker_process_running(container_name):
            logging.error("[-] Emulation process exited before producing a result.")
            return False

        if time.time() >= next_update:
            elapsed = int(time.time() - started)
            logging.info("[*] Waiting for emulation result... %ss elapsed", elapsed)
            if docker_path_exists(container_name, log_path):
                try:
                    log_tail = check_output([
                        "docker", "exec", container_name, "bash", "-lc",
                        "tail -n 5 {}".format(shlex.quote(log_path)),
                    ]).decode().strip()
                    if log_tail:
                        logging.info("%s", log_tail)
                except sp.CalledProcessError:
                    pass
            next_update = time.time() + 30

        time.sleep(2)

    return False


def wait_for_debug_shell_ready(container_name, run_log, timeout=300):
    marker = "Debug shell is enabled"
    started = time.time()
    next_update = started

    while time.time() - started < timeout:
        if docker_file_contains(container_name, run_log, marker):
            return True

        if time.time() - started > 10 and not docker_process_running(container_name):
            logging.warning("[*] Emulation process exited before the debug shell ready marker.")
            return False

        if time.time() >= next_update:
            elapsed = int(time.time() - started)
            logging.info("[*] Waiting for debug shell readiness... %ss elapsed", elapsed)
            next_update = time.time() + 30

        time.sleep(2)

    logging.warning("[*] Timed out waiting for the debug shell ready marker.")
    return False


def wait_for_tcp(container_name, host, port, timeout=120):
    started = time.time()
    while time.time() - started < timeout:
        cmd = "nc -z -w 2 {} {}".format(shlex.quote(host), int(port))
        if sp.call(
            ["docker", "exec", container_name, "bash", "-lc", cmd],
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        ) == 0:
            return True
        time.sleep(2)
    return False


def debug_shell_command(container_name, guest_ip, commands, timeout=12):
    quoted_commands = shlex.quote(commands)
    cmd = "printf %s {} | timeout {} nc -w {} {} 31337".format(
        quoted_commands,
        int(timeout),
        int(timeout),
        shlex.quote(guest_ip),
    )
    result = sp.run(
        ["docker", "exec", container_name, "bash", "-lc", cmd],
        stdout=sp.PIPE,
        stderr=sp.STDOUT,
        check=False,
    )
    return result.stdout.decode(errors="replace")


def parse_netstat_ports(output, guest_ip):
    ports = set()

    for raw_line in output.splitlines():
        line = raw_line.strip().replace("\r", "")
        parts = line.split()
        if len(parts) < 4 or not parts[0].lower().startswith("tcp"):
            continue
        if "LISTEN" not in line.upper():
            continue

        local = parts[3]
        if local.startswith("[") and "]:" in local:
            host, port_text = local.rsplit("]:", 1)
            host = host[1:]
        elif ":" in local:
            host, port_text = local.rsplit(":", 1)
        else:
            continue

        if not port_text.isdigit():
            continue

        host = host.strip("[]")
        if host.startswith("127.") or host in ("localhost", "::1"):
            continue
        if host not in ("", "*", "0.0.0.0", "::", ":::", guest_ip):
            continue

        port = int(port_text)
        if 0 < port < 65536:
            ports.add(port)

    return sorted(ports)


def service_for_port(port):
    name, hint = KNOWN_SERVICE_HINTS.get(port, ("tcp-{}".format(port), "nc {host} {port}"))
    return {
        "name": name,
        "guest_port": port,
        "container_port": port,
        "hint": hint,
    }


def discover_services(container_name, guest_ip):
    if not wait_for_tcp(container_name, guest_ip, 31337, timeout=180):
        logging.warning("[*] Debug shell is not reachable; using default port mapping fallback.")
        return list(DEFAULT_SERVICES), "fallback"

    commands = (
        "/firmadyne/busybox netstat -lnt\n"
        "/firmadyne/busybox netstat -ln\n"
        "exit\n"
    )
    discovered_ports = set()
    stable_attempts = 0
    for attempt in range(1, 16):
        output = debug_shell_command(container_name, guest_ip, commands)
        ports = set(parse_netstat_ports(output, guest_ip))
        new_ports = ports - discovered_ports
        if new_ports:
            discovered_ports.update(new_ports)
            stable_attempts = 0
        elif discovered_ports:
            stable_attempts += 1

        if discovered_ports and stable_attempts >= 3:
            break

        logging.info("[*] Polling debug shell port list (%d/15).", attempt)
        time.sleep(3)

    if not discovered_ports:
        logging.warning("[*] Debug shell returned no TCP listeners; using default port mapping fallback.")
        return list(DEFAULT_SERVICES), "fallback"
    ports = set(discovered_ports)
    ports.add(31337)

    services = []
    for port in sorted(ports):
        if wait_for_tcp(container_name, guest_ip, port, timeout=6):
            services.append(service_for_port(port))

    logging.info("[*] Debug shell discovered TCP listeners: %s", ", ".join(str(port) for port in sorted(ports)))
    if not services:
        logging.warning("[*] No discovered TCP listener was reachable from the emulator container.")
    return services, "debug-shell"


def start_forwarders(container_name, iid, guest_ip, services):
    for service in services:
        log_path = "/work/FirmAE/scratch/{}/forward-{}.log".format(iid, service["name"])
        cmd = (
            "nohup socat "
            "TCP-LISTEN:{container_port},fork,reuseaddr,bind=0.0.0.0 "
            "TCP:{guest_ip}:{guest_port} "
            "> {log_path} 2>&1 &"
        ).format(
            container_port=service["container_port"],
            guest_ip=shlex.quote(guest_ip),
            guest_port=service["guest_port"],
            log_path=shlex.quote(log_path),
        )
        docker_exec(container_name, cmd, detach=False)


def host_port_available(port):
    sockets = []
    try:
        for family, address in ((socket.AF_INET, "0.0.0.0"), (socket.AF_INET6, "::")):
            sock = socket.socket(family, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if family == socket.AF_INET6:
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            sock.bind((address, int(port)))
            sockets.append(sock)
        return True
    except OSError:
        return False
    finally:
        for sock in sockets:
            sock.close()


def build_publish_args(publish_container_name, services, script, prefer_same_host_ports):
    args = [
        "docker", "run", "-dit", "--rm",
        "--name", publish_container_name,
    ]
    for service in services:
        host_port = service["guest_port"]
        if prefer_same_host_ports and host_port_available(host_port):
            args.extend(["-p", "{}:{}/tcp".format(host_port, service["container_port"])])
        else:
            if prefer_same_host_ports:
                logging.warning(
                    "[*] Host port %s is unavailable; Docker will assign a random host port.",
                    host_port,
                )
            args.extend(["-p", "{}/tcp".format(service["container_port"])])
    args.extend(["fcore", "bash", "-lc", script])
    return args


def start_publish_container(container_name, services):
    if not services:
        return None

    publish_container_name = "{}_ports".format(container_name)
    main_ip = docker_bridge_ip(container_name)

    sp.call(
        ["docker", "rm", "-f", publish_container_name],
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL,
    )

    script_lines = ["set -e"]
    for service in services:
        script_lines.append(
            "socat TCP-LISTEN:{port},fork,reuseaddr,bind=0.0.0.0 TCP:{main_ip}:{port} &".format(
                port=service["container_port"],
                main_ip=shlex.quote(main_ip),
            )
        )
    script_lines.append("wait")
    script = "\n".join(script_lines)

    args = build_publish_args(publish_container_name, services, script, True)
    args[6:6] = ["--label", "firmae.parent={}".format(container_name)]
    try:
        check_output(args)
    except sp.CalledProcessError as exc:
        logging.warning("[*] Same-port publishing failed; retrying with random host ports.")
        if exc.output:
            logging.warning("%s", exc.output.decode(errors="replace").strip())
        sp.call(
            ["docker", "rm", "-f", publish_container_name],
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )
        args = build_publish_args(publish_container_name, services, script, False)
        args[6:6] = ["--label", "firmae.parent={}".format(container_name)]
        check_output(args)
    return publish_container_name


def print_access_info(container_name, publish_container_name, guest_ip, services, service_source):
    print("")
    print("[+] Firmware emulation is running.")
    print("[+] Container: {}".format(container_name))
    if publish_container_name:
        print("[+] Port forwarder: {}".format(publish_container_name))
    print("[+] Firmware IP: {}".format(guest_ip))
    print("[+] Service discovery: {}".format(service_source))
    print("[+] Published services:")

    for service in services:
        if not publish_container_name:
            continue

        endpoint = published_endpoint(publish_container_name, service["container_port"])
        if not endpoint:
            continue

        host, port = endpoint
        display_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
        hint = service["hint"].format(host=display_host, port=port)
        print("    {:9s} host {}:{} -> firmware {}:{}    {}".format(
            service["name"],
            host,
            port,
            guest_ip,
            service["guest_port"],
            hint,
        ))

    if not services:
        print("    none")

    print("")
    if publish_container_name:
        print("[*] Stop it with: sudo docker stop {} {}".format(container_name, publish_container_name))
    else:
        print("[*] Stop it with: sudo docker stop {}".format(container_name))


def start_emulation(firmware_path, enable_aslr=False):
    firmware_path = os.path.abspath(firmware_path)
    if not os.path.isfile(firmware_path):
        raise FileNotFoundError(firmware_path)

    firmware = os.path.basename(firmware_path)
    iid = util.get_iid(firmware_path)
    container_name = safe_container_name(iid, firmware_path)
    container_firmware = "/work/firmwares/{}".format(firmware)

    docker_run(container_name)
    logging.info("[*] Started container %s", container_name)

    try:
        docker_exec(container_name, "mkdir -p /work/firmwares /work/FirmAE/scratch /work/FirmAE/images")
        check_output(["docker", "cp", firmware_path, "{}:{}".format(container_name, container_firmware)])

        run_log = "/work/FirmAE/scratch/{}.log".format(firmware)
        run_cmd = "cd /work/FirmAE && FIRMAE_ASLR={} FIRMAE_NONINTERACTIVE_DEBUG=true ./run.sh -d '' {} > {} 2>&1".format(
            "true" if enable_aslr else "false",
            shlex.quote(container_firmware),
            shlex.quote(run_log),
        )
        docker_exec(container_name, run_cmd, detach=True)
        logging.info("[*] Emulation started for %s", firmware)

        if not wait_for_result(container_name, iid):
            raise RuntimeError("emulation did not report a successful result")

        guest_ip_path = "/work/FirmAE/scratch/{}/ip".format(iid)
        guest_ip = docker_read_file(container_name, guest_ip_path)
        wait_for_debug_shell_ready(container_name, run_log)
        services, service_source = discover_services(container_name, guest_ip)
        start_forwarders(container_name, iid, guest_ip, services)
        publish_container_name = start_publish_container(container_name, services)
        print_access_info(container_name, publish_container_name, guest_ip, services, service_source)
        return 0
    except Exception:
        logging.exception("[-] Failed to start firmware emulation")
        logging.error("[*] Container %s is left running for debugging.", container_name)
        logging.error("[*] Stop it with: sudo docker stop %s", container_name)
        return 1


def main():
    args = sys.argv[1:]
    enable_aslr = False

    if not args or any(arg in ("-h", "--help") for arg in args):
        print_usage(sys.argv[0])
        return 1 if not args else 0

    if "--aslr" in args:
        enable_aslr = True
        args.remove("--aslr")

    if "--no-aslr" in args:
        enable_aslr = False
        args.remove("--no-aslr")

    if len(args) != 1:
        print_usage(sys.argv[0])
        return 1

    return start_emulation(args[0], enable_aslr)


if __name__ == "__main__":
    sys.exit(main())
