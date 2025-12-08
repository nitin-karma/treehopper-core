# tests/unit/test_port_hash.py
# import hashlib
from treehopper.treehopper_chains import derive_chain_port


def test_derive_chain_port_stable():
    a = derive_chain_port("cancel_test_chain-1234")
    b = derive_chain_port("cancel_test_chain-1234")
    assert isinstance(a, int)
    assert a == b
    assert 20000 <= a < 25000
