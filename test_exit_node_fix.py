#!/usr/bin/env python3
"""Unit tests covering exit node helper utilities."""

from gui import MainWindow
from tailscale_client import Device


def _device(**kwargs) -> Device:
    defaults = dict(
        name="node1",
        tailnet_ips=["100.64.0.2"],
        os="linux",
        online=True,
        exit_node_option=True,
        is_exit_node=False,
        hostinfo={},
        device_id="dev-1",
    )
    defaults.update(kwargs)
    return Device(**defaults)


def test_preferred_exit_node_prefers_hostname():
    device = _device(hostinfo={"Hostname": "exit-host"}, name="alias", tailnet_ips=["100.64.0.2"], device_id="dev-123")
    result = MainWindow._preferred_exit_node_argument(device)
    assert result == "exit-host"


def test_preferred_exit_node_falls_back_to_name():
    device = _device(name="node-alias", hostinfo={})
    result = MainWindow._preferred_exit_node_argument(device)
    assert result == "node-alias"


def test_preferred_exit_node_uses_ip_when_needed():
    device = _device(name=None, hostinfo={}, tailnet_ips=["100.64.10.5"], device_id="dev-ip")
    result = MainWindow._preferred_exit_node_argument(device)
    assert result == "100.64.10.5"


def test_preferred_exit_node_falls_back_to_id():
    device = _device(name=None, hostinfo={}, tailnet_ips=[], device_id="dev-final")
    result = MainWindow._preferred_exit_node_argument(device)
    assert result == "dev-final"


def test_exit_aliases_contains_all_identifiers():
    device = _device(
        name="node-alias",
        tailnet_ips=["100.64.0.2", "fd7a:115c:a1e0:ab12:4843:cd96:6253:1234"],
        device_id="dev-xyz",
        hostinfo={"Hostname": "host.local", "DNSName": "host.tail"},
    )
    aliases = MainWindow._exit_aliases_for_device(device)
    expected = {
        "node-alias",
        "100.64.0.2",
        "fd7a:115c:a1e0:ab12:4843:cd96:6253:1234",
        "dev-xyz",
        "host.local",
        "host.tail",
    }
    assert expected.issubset(aliases)


def test_format_exit_label_includes_ips():
    device = _device(name="Node", tailnet_ips=["100.64.0.20"], hostinfo={})
    label = MainWindow._format_exit_label(device, "Node")
    assert label == "Node – 100.64.0.20"


def test_format_exit_label_without_ips_uses_name_only():
    device = _device(name="NodeOnly", tailnet_ips=[], hostinfo={})
    label = MainWindow._format_exit_label(device, "NodeOnly")
    assert label == "NodeOnly"