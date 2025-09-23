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

