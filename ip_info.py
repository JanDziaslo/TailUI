import threading
import time
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

import requests


@dataclass
class PublicIPInfo:
    ip: str
    org: Optional[str] = None
    asn: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    loc: Optional[str] = None
    raw: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


def _normalize_asn(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = value.strip()
    if v.startswith('AS'):
        # Upewnij się że po AS są cyfry
        num = v[2:].split()[0]
        if num.isdigit():
            return 'AS' + num
        return v
    # Jeśli to czyste cyfry – dodaj prefix
    if v.isdigit():
        return 'AS' + v
    return v


class PublicIPFetcher:
    """Pobiera dane o publicznym IP z jednego z publicznych endpointów.
    Używa prostego cache z TTL by nie przeciążać API.
    """

    def __init__(self, ttl: int = 300):
        self.ttl = ttl
        self._cache: Optional[PublicIPInfo] = None
        self._cache_time: float = 0.0
        self._lock = threading.Lock()

    def _fetch(self) -> Optional[PublicIPInfo]:
        # Próby kilku źródeł w kolejności
        endpoints = [
            ("https://ipinfo.io/json", self._parse_ipinfo),
            ("https://ipapi.co/json", self._parse_ipapi),
            ("https://ifconfig.co/json", self._parse_ifconfig),
        ]
        headers = {"User-Agent": "tailscale-gui/1.0"}
        for url, parser in endpoints:
            try:
                r = requests.get(url, timeout=5, headers=headers)
                if r.status_code == 200:
                    return parser(r.json())
            except Exception:
                continue
        return None

    @staticmethod
    def _parse_ipinfo(data: Dict[str, Any]) -> PublicIPInfo:
        org = data.get('org')
        asn_raw = data.get('asn')
        asn = _normalize_asn(asn_raw)
        # Jeśli brak osobnego ASN, spróbuj wydobyć pierwszy token z org
        if not asn and org:
            first = org.split()[0]
            norm = _normalize_asn(first)
            if norm and norm.startswith('AS'):
                asn = norm
        return PublicIPInfo(
            ip=data.get('ip', ''),
            org=org,
            asn=asn,
            city=data.get('city'),
            region=data.get('region'),
            country=data.get('country'),
            loc=data.get('loc'),
            raw=data,
        )

    @staticmethod
    def _parse_ipapi(data: Dict[str, Any]) -> PublicIPInfo:
        asn = _normalize_asn(data.get('asn'))
        return PublicIPInfo(
            ip=data.get('ip', ''),
            org=data.get('org') or data.get('org_name'),
            asn=asn,
            city=data.get('city'),
            region=data.get('region'),
            country=data.get('country'),
            loc=f"{data.get('latitude')},{data.get('longitude')}",
            raw=data,
        )

    @staticmethod
    def _parse_ifconfig(data: Dict[str, Any]) -> PublicIPInfo:
        raw_asn = data.get('asn')
        if raw_asn is not None:
            raw_asn = str(raw_asn)
        asn = _normalize_asn(raw_asn)
        return PublicIPInfo(
            ip=data.get('ip', ''),
            org=data.get('asn_org') or data.get('org'),
            asn=asn,
            city=data.get('city'),
            region=data.get('region_name') or data.get('region'),
            country=data.get('country'),
            loc=f"{data.get('latitude')},{data.get('longitude')}",
            raw=data,
        )

    def get_public_ip(self, force: bool = False) -> Optional[PublicIPInfo]:
        with self._lock:
            now = time.time()
            if (not force and self._cache and (now - self._cache_time) < self.ttl):
                return self._cache
            info = self._fetch()
            if info:
                self._cache = info
                self._cache_time = now
            return info
