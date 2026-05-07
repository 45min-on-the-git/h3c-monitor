"""ACL CLI 输出解析测试"""

from driver.h3c_ssh import H3CSSHDriver


def _make_driver():
    return H3CSSHDriver({
        "device_type": "hp_comware",
        "ip": "10.0.0.1",
        "username": "x",
        "password": "x",
        "device_category": "switch",
    })


def test_parse_advanced_acl():
    """解析 Advanced IPv4 ACL（Comware V7 实际格式）"""
    output = """Advanced IPv4 ACL 3000, named my-acl, 3 rules,
ACL's step is 5
 rule 5 permit tcp source 192.168.1.0 0.0.0.255 destination any destination-port eq 80 (10 times matched)
 rule 10 deny ip source 10.0.0.0 0.255.255.255 destination any
 rule 15 permit ip source any destination any
"""
    d = _make_driver()
    rules = d._parse_acls(output)
    assert len(rules) == 3

    r1 = rules[0]
    assert r1["acl_number"] == 3000
    assert r1["rule_id"] == 5
    assert r1["action"] == "permit"
    assert r1["protocol"] == "tcp"
    assert r1["source"] == "192.168.1.0 0.0.0.255"

    r2 = rules[1]
    assert r2["rule_id"] == 10
    assert r2["action"] == "deny"
    assert r2["protocol"] == "ip"

    r3 = rules[2]
    assert r3["rule_id"] == 15
    assert r3["action"] == "permit"


def test_parse_basic_acl():
    """解析 Basic ACL"""
    output = """Basic ACL  2000, named flow, 2 rules,
ACL's step is 5
 rule 0 permit
 rule 5 permit source 1.1.1.1 0 (5 times matched)
"""
    d = _make_driver()
    rules = d._parse_acls(output)
    assert len(rules) == 2

    assert rules[0]["acl_number"] == 2000
    assert rules[0]["rule_id"] == 0
    assert rules[0]["action"] == "permit"
    assert rules[0]["protocol"] == "ip"  # 无协议默认 ip
    assert rules[0]["source"] == "any"

    assert rules[1]["rule_id"] == 5
    assert rules[1]["source"] == "1.1.1.1 0"


def test_parse_rule_no_protocol():
    """rule 0 permit 无协议参数，默认 ip"""
    output = """Advanced ACL  3000,
 rule 0 permit
 rule 5 deny ip source any destination any
"""
    d = _make_driver()
    rules = d._parse_acls(output)
    assert len(rules) == 2
    assert rules[0]["protocol"] == "ip"


def test_parse_match_count_suffix():
    """(N times matched) 后缀不影响解析"""
    output = """Advanced ACL 3000,
 rule 5 permit ip source any destination any (999 times matched)
"""
    d = _make_driver()
    rules = d._parse_acls(output)
    assert len(rules) == 1
    assert rules[0]["rule_id"] == 5
    assert rules[0]["action"] == "permit"


def test_parse_comment_line():
    """rule N comment 行被跳过"""
    output = """Advanced ACL 3000,
 rule 0 permit ip
 rule 5 comment This is a comment
 rule 10 deny ip source any destination any
"""
    d = _make_driver()
    rules = d._parse_acls(output)
    assert len(rules) == 2
    assert rules[0]["rule_id"] == 0
    assert rules[1]["rule_id"] == 10


def test_parse_empty_output():
    """空输出返回空列表"""
    d = _make_driver()
    assert d._parse_acls("") == []
    assert d._parse_acls("No ACL exists") == []


def test_parse_multiple_acls():
    """多个 ACL 混合解析"""
    output = """Basic ACL  2000, named a, 1 rule,
 rule 0 permit source 1.1.1.1 0

Advanced IPv4 ACL 3001, named b, 1 rule,
 rule 5 deny tcp source any destination any destination-port eq 22
"""
    d = _make_driver()
    rules = d._parse_acls(output)
    assert len(rules) == 2
    assert rules[0]["acl_number"] == 2000
    assert rules[1]["acl_number"] == 3001
