import json
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple


class TailscaleError(Exception):
    pass


def _which(executable: str) -> Optional[str]:
    return shutil.which(executable)


def _run(cmd: List[str], timeout: int = 15) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        return 124, '', f"Timeout: {e}"


@dataclass
class Device:
    name: str
    tailnet_ips: List[str] = field(default_factory=list)
    os: Optional[str] = None
    online: bool = True
    exit_node_option: bool = False
    is_exit_node: bool = False
    hostinfo: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Status:
    raw: Dict[str, Any]
    backend_state: str
    self_device: Optional[Device]
    devices: List[Device]
    exit_nodes: List[Device]
    connected: bool


class TailscaleClient:
    def __init__(self, executable: str = 'tailscale'):
        self.executable = executable
        if not _which(executable):
            raise TailscaleError("Nie znaleziono polecenia 'tailscale' w PATH.")

    def status(self) -> Status:
        code, out, err = _run([self.executable, 'status', '--json'])
        if code != 0:
            raise TailscaleError(f"Błąd pobierania statusu tailscale: {err or out}")
        try:
            data = json.loads(out)
        except json.JSONDecodeError as e:
            raise TailscaleError(f"Niepoprawny JSON statusu: {e}\n{out[:500]}")

        backend_state = data.get('BackendState') or data.get('BackendState', '')
        self_peer = data.get('Self', {})
        self_device = None
        devices: List[Device] = []
        peers = data.get('Peer', {}) or data.get('Peers', {}) or {}

        def parse_peer(key: str, value: Dict[str, Any]) -> Device:
            # In JSON structure keys maybe device ID, value is details
            hostinfo = value.get('Hostinfo') or value.get('HostInfo') or {}
            name = hostinfo.get('Hostname') or value.get('DNSName') or key
            addrs = value.get('TailscaleIPs') or value.get('TailscaleIPs', [])
            if isinstance(addrs, str):
                addrs = [addrs]
            exit_option = bool(value.get('ExitNodeOption') or value.get('ExitNodeAllowed', False))
            is_exit = bool(value.get('ExitNode', False))
            online = not bool(value.get('Online') is False)
            os_name = hostinfo.get('OS') or hostinfo.get('OSVersion')
            return Device(name=name, tailnet_ips=addrs or [], os=os_name, online=online,
                          exit_node_option=exit_option, is_exit_node=is_exit, hostinfo=hostinfo)

        # Self device
        if self_peer:
            self_device = parse_peer('self', self_peer)
            devices.append(self_device)

        for peer_id, peer_val in peers.items():
            devices.append(parse_peer(peer_id, peer_val))

        exit_nodes = [d for d in devices if d.exit_node_option]
        # Nowa definicja połączenia: Running + posiadanie IP
        connected = backend_state.lower() == 'running' and bool(self_device and self_device.tailnet_ips)

        return Status(raw=data, backend_state=backend_state, self_device=self_device, devices=devices,
                      exit_nodes=exit_nodes, connected=connected)

    def is_connected(self) -> bool:
        try:
            st = self.status()
            return st.connected
        except TailscaleError:
            return False

    def up(self, extra_args: Optional[List[str]] = None) -> None:
        args = [self.executable, 'up']
        if extra_args:
            args.extend(extra_args)
        code, out, err = _run(args, timeout=60)
        if code != 0:
            raise TailscaleError(f"Błąd włączania tailscale: {err or out}")

    def down(self) -> None:
        code, out, err = _run([self.executable, 'down'])
        if code != 0:
            raise TailscaleError(f"Błąd wyłączania tailscale: {err or out}")

    def set_exit_node(self, exit_node: Optional[str]) -> None:
        # exit_node może być None (wyłączenie) lub nazwa/IP
        if exit_node:
            self.up(['--exit-node', exit_node])
        else:
            # Wyłącz exit node bez resetowania całej konfiguracji – podając pusty exit node
            self.up(['--exit-node='])

    def current_exit_node(self) -> Optional[str]:
        st = self.status()
        for d in st.devices:
            if d.is_exit_node:
                return d.name
        return None


# Helper funkcja do próbnego sprawdzenia dostępności tailscale w środowisku testowym

def tailscale_available() -> bool:
    return _which('tailscale') is not None
