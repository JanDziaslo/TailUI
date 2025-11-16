import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, Iterable


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


def _extract_short_hostname(full_name: str) -> str:
    """
    Wyodrębnia krótką nazwę hosta z pełnej nazwy DNS.
    Np. 'kubuntu-pc.tail1234.ts.net' -> 'kubuntu-pc'
    """
    if not full_name:
        return full_name
    # Jeśli nazwa zawiera kropkę, weź tylko pierwszą część (przed kropką)
    if '.' in full_name:
        return full_name.split('.')[0]
    return full_name


@dataclass
class Device:
    name: str
    tailnet_ips: List[str] = field(default_factory=list)
    os: Optional[str] = None
    online: bool = True
    exit_node_option: bool = False
    is_exit_node: bool = False
    hostinfo: Dict[str, Any] = field(default_factory=dict)
    device_id: Optional[str] = None


@dataclass
class Status:
    raw: Dict[str, Any]
    backend_state: str
    self_device: Optional[Device]
    devices: List[Device]
    exit_nodes: List[Device]
    connected: bool
    active_exit_node: Optional[Device]


class TailscaleClient:
    def __init__(self, executable: str = 'tailscale'):
        resolved = _which(executable)
        if resolved:
            self.executable = resolved
        elif os.path.isabs(executable) and os.path.exists(executable):
            self.executable = executable
        else:
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
            raw_name = hostinfo.get('Hostname') or value.get('DNSName') or key
            # Wyodrębnij krótką nazwę hosta (usuń sufiks tailscale)
            name = _extract_short_hostname(raw_name)
            addrs = value.get('TailscaleIPs') or value.get('TailscaleIPs', [])
            if isinstance(addrs, str):
                addrs = [addrs]
            exit_option = bool(value.get('ExitNodeOption') or value.get('ExitNodeAllowed', False))
            is_exit = bool(value.get('ExitNode', False))
            online = not bool(value.get('Online') is False)

            # Pobierz system operacyjny - sprawdź różne możliwe pola
            os_name = (
                hostinfo.get('OS') or
                hostinfo.get('OSVersion') or
                hostinfo.get('OperatingSystem') or
                hostinfo.get('OSName') or
                value.get('OS') or
                value.get('OSVersion')
            )

            device_id = value.get('ID') or value.get('Id') or key
            return Device(name=name, tailnet_ips=addrs or [], os=os_name, online=online,
                          exit_node_option=exit_option, is_exit_node=is_exit,
                          hostinfo=hostinfo, device_id=device_id)

        # Self device
        if self_peer:
            self_device = parse_peer(self_peer.get('ID') or 'self', self_peer)
            devices.append(self_device)

        devices_by_id: Dict[str, Device] = {}
        if self_device and self_device.device_id:
            devices_by_id[self_device.device_id] = self_device

        for peer_id, peer_val in peers.items():
            device = parse_peer(peer_id, peer_val)
            devices.append(device)
            if device.device_id:
                devices_by_id[device.device_id] = device

        exit_nodes = [d for d in devices if d.exit_node_option]

        def _collect_exit_node_ids(status_dict: Dict[str, Any]) -> Iterable[str]:
            candidates: List[str] = []
            for key in ('ExitNodeID', 'ExitNodeId', 'ID', 'Id', 'PeerID', 'PeerId'):
                val = status_dict.get(key)
                if isinstance(val, str) and val:
                    candidates.append(val)
            exit_info = status_dict.get('ExitNode')
            if isinstance(exit_info, dict):
                for key in ('ID', 'Id', 'NodeID', 'NodeId', 'PeerID', 'PeerId'):
                    val = exit_info.get(key)
                    if isinstance(val, str) and val:
                        candidates.append(val)
            id_list = status_dict.get('ExitNodeIDs') or status_dict.get('ExitNodeIds')
            if isinstance(id_list, list):
                for item in id_list:
                    if isinstance(item, str) and item:
                        candidates.append(item)
            return candidates

        exit_status = data.get('ExitNodeStatus') or {}
        if not isinstance(exit_status, dict):
            exit_status = {}

        active_ids = []
        if exit_status and exit_status.get('Active') is False:
            active_ids = []
        else:
            active_ids = list(_collect_exit_node_ids(exit_status))

        active_exit_node: Optional[Device] = None

        for candidate_id in active_ids:
            device = devices_by_id.get(candidate_id)
            if device:
                device.is_exit_node = True
                active_exit_node = device
                break

        if not active_exit_node:
            # Fallback do wcześniejszego heurystycznego pola ExitNode
            for device in devices:
                if device.is_exit_node:
                    active_exit_node = device
                    break

        # Nowa definicja połączenia: Running + posiadanie IP
        connected = backend_state.lower() == 'running' and bool(self_device and self_device.tailnet_ips)

        return Status(raw=data, backend_state=backend_state, self_device=self_device, devices=devices,
                      exit_nodes=exit_nodes, connected=connected, active_exit_node=active_exit_node)

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

    def set_exit_node(self, exit_node: Optional[str], *, allow_sudo: bool = True) -> None:
        """
        Ustawia exit node wykorzystując `tailscale set --exit-node`.

        Jeśli pierwsza próba zakończy się błędem uprawnień, a `sudo` jest dostępne,
        podejmowana jest druga próba z prefiksem `sudo` (jeśli allow_sudo=True).
        """

        if exit_node:
            base_cmd = [self.executable, 'set', '--accept-routes=true', f'--exit-node={exit_node}']
        else:
            base_cmd = [self.executable, 'set', '--accept-routes=false', '--exit-node=']

        code, out, err = _run(base_cmd)
        if code == 0:
            return

        combined = (err or out or '').strip()

        if allow_sudo and self._should_retry_with_sudo(code, combined):
            sudo_path = _which('sudo')
            if sudo_path:
                sudo_cmd = [sudo_path] + base_cmd
                sudo_code, sudo_out, sudo_err = _run(sudo_cmd)
                if sudo_code == 0:
                    return
                combined = (sudo_err or sudo_out or combined).strip()

        raise TailscaleError(f"Błąd ustawiania exit node: {combined}")

    @staticmethod
    def _should_retry_with_sudo(exit_code: int, message: str) -> bool:
        if exit_code in (0, 124):  # 124 → timeout, nie próbujemy sudo automatycznie
            return False
        lowered = message.lower()
        tokens = (
            'permission denied',
            'must be root',
            'requires root',
            'requires sudo',
            'sudo',
            'operation not permitted',
        )
        return any(token in lowered for token in tokens)

    def current_exit_node(self) -> Optional[str]:
        st = self.status()
        if st.active_exit_node:
            return st.active_exit_node.name
        for d in st.devices:
            if d.is_exit_node:
                return d.name
        return None


# Helper funkcja do próbnego sprawdzenia dostępności tailscale w środowisku testowym

def tailscale_available() -> bool:
    return _which('tailscale') is not None

