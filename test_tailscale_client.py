import json
import types
from typing import List

import tailscale_client as tc


class DummyProc:
    def __init__(self, code: int, out: str, err: str = ""):
        self.returncode = code
        self.stdout = out
        self.stderr = err


def test_status_parsing(monkeypatch):
    # Udajemy że binarka istnieje
    monkeypatch.setattr(tc, '_which', lambda x: '/usr/bin/tailscale')

    sample_json = {
        "BackendState": "Running",
        "Self": {
            "Hostinfo": {"Hostname": "myhost", "OS": "linux"},
            "TailscaleIPs": ["100.64.0.1"]
        },
        "Peer": {
            "peer1": {
                "Hostinfo": {"Hostname": "exitnode", "OS": "linux"},
                "TailscaleIPs": ["100.64.0.2"],
                "ExitNodeOption": True,
                "ExitNode": True
            },
            "peer2": {
                "Hostinfo": {"Hostname": "workstation", "OS": "linux"},
                "TailscaleIPs": ["100.64.0.3"],
                "Online": False
            }
        }
    }

    def fake_run(cmd: List[str], timeout: int = 15):
        return 0, json.dumps(sample_json), ""

    monkeypatch.setattr(tc, '_run', fake_run)

    client = tc.TailscaleClient()
    status = client.status()

    assert status.backend_state == 'Running'
    assert status.connected is True
    assert status.self_device is not None
    assert len(status.devices) == 3  # self + 2 peers
    exit_nodes = [d for d in status.devices if d.exit_node_option]
    assert len(exit_nodes) == 1
    assert exit_nodes[0].is_exit_node is True
    assert status.devices[2].online is False


def test_current_exit_node(monkeypatch):
    monkeypatch.setattr(tc, '_which', lambda x: '/usr/bin/tailscale')
    sample_json = {
        "BackendState": "Running",
        "Self": {
            "Hostinfo": {"Hostname": "myhost", "OS": "linux"},
            "TailscaleIPs": ["100.64.0.1"]
        },
        "Peer": {
            "peer1": {
                "Hostinfo": {"Hostname": "exitnode", "OS": "linux"},
                "TailscaleIPs": ["100.64.0.2"],
                "ExitNodeOption": True,
                "ExitNode": True
            }
        }
    }

    monkeypatch.setattr(tc, '_run', lambda cmd, timeout=15: (0, json.dumps(sample_json), ""))
    client = tc.TailscaleClient()
    assert client.current_exit_node() == 'exitnode'


def test_exit_node_status_detection(monkeypatch):
    monkeypatch.setattr(tc, '_which', lambda x: '/usr/bin/tailscale')
    sample_json = {
        "BackendState": "Running",
        "Self": {
            "ID": "self1",
            "Hostinfo": {"Hostname": "myhost", "OS": "linux"},
            "TailscaleIPs": ["100.64.0.1"]
        },
        "ExitNodeStatus": {
            "Active": True,
            "ExitNodeID": "peer1"
        },
        "Peer": {
            "peer1": {
                "ID": "peer1",
                "Hostinfo": {"Hostname": "exitnode", "OS": "linux"},
                "TailscaleIPs": ["100.64.0.2"],
                "ExitNodeOption": True
            }
        }
    }

    monkeypatch.setattr(tc, '_run', lambda cmd, timeout=15: (0, json.dumps(sample_json), ""))
    client = tc.TailscaleClient()
    status = client.status()

    assert status.active_exit_node is not None
    assert status.active_exit_node.name == 'exitnode'
    assert status.active_exit_node.device_id == 'peer1'
    assert status.active_exit_node.is_exit_node is True


def test_set_exit_node_fallback_to_sudo(monkeypatch):
    def fake_which(name):
        if name == 'tailscale':
            return '/usr/bin/tailscale'
        if name == 'sudo':
            return '/usr/bin/sudo'
        return None

    monkeypatch.setattr(tc, '_which', fake_which)

    calls = []

    def fake_run(cmd, timeout=15):
        calls.append(cmd)
        if cmd and cmd[0].endswith('sudo'):
            return 0, '', ''
        return 1, '', 'permission denied'

    monkeypatch.setattr(tc, '_run', fake_run)

    client = tc.TailscaleClient()
    client.set_exit_node('exitnode')

    assert calls[0] == ['/usr/bin/tailscale', 'set', '--accept-routes=true', '--exit-node=exitnode']
    assert calls[1][0].endswith('sudo')
    assert calls[1][1:] == ['/usr/bin/tailscale', 'set', '--accept-routes=true', '--exit-node=exitnode']

