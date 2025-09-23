import ip_info


def test_public_ip_fetcher_parsing_ipinfo(monkeypatch):
    sample = {
        "ip": "203.0.113.10",
        "org": "AS123 ExampleOrg",
        "asn": "AS123",
        "city": "CityX",
        "region": "RegionY",
        "country": "PL",
        "loc": "52.00,21.00"
    }

    class Resp:
        status_code = 200

        def json(self):
            return sample

    def fake_get(url, timeout=5, headers=None):
        return Resp()

    monkeypatch.setattr(ip_info.requests, 'get', fake_get)

    fetcher = ip_info.PublicIPFetcher(ttl=300)
    info = fetcher.get_public_ip(force=True)
    assert info.ip == sample['ip']
    assert info.city == 'CityX'
    assert info.country == 'PL'
    assert info.org.startswith('AS123')


def test_public_ip_fetcher_fallback(monkeypatch):
    # Pierwszy endpoint rzuca wyjątek, drugi zwraca dane
    sample_second = {
        "ip": "198.51.100.5",
        "org": "AS999 SecondOrg",
        "asn": "AS999",
        "city": "Town",
        "region": "Region",
        "country": "DE",
        "latitude": 50.0,
        "longitude": 8.0,
    }

    call_count = {"n": 0}

    class Resp2:
        status_code = 200

        def json(self):
            return sample_second

    def fake_get(url, timeout=5, headers=None):
        call_count['n'] += 1
        if call_count['n'] == 1:  # ipinfo (pierwszy) - rzuć wyjątek
            raise RuntimeError('network error')
        if call_count['n'] == 2:  # ipapi (drugi) - sukces
            return Resp2()
        raise RuntimeError('should not reach third when second ok')

    monkeypatch.setattr(ip_info.requests, 'get', fake_get)

    fetcher = ip_info.PublicIPFetcher(ttl=300)
    info = fetcher.get_public_ip(force=True)
    assert info.ip == sample_second['ip']
    assert info.country == 'DE'


def test_public_ip_fetcher_cache(monkeypatch):
    sample = {"ip": "203.0.113.20"}
    calls = {"n": 0}

    class Resp:
        status_code = 200

        def json(self):
            return sample

    def fake_get(url, timeout=5, headers=None):
        calls['n'] += 1
        return Resp()

    monkeypatch.setattr(ip_info.requests, 'get', fake_get)
    fetcher = ip_info.PublicIPFetcher(ttl=300)
    first = fetcher.get_public_ip(force=True)
    second = fetcher.get_public_ip(force=False)
    assert first.ip == second.ip == sample['ip']
    assert calls['n'] == 1  # cache użyty

