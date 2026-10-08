import hashlib
from app.payments.ledger import compute_merkle_proof, verify_merkle_proof, compute_merkle_root


def _h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def test_single_leaf_empty_proof_root_equals_leaf():
    leaf = _h("a")
    leaves = [leaf]
    proof = compute_merkle_proof(leaves, 0)
    assert proof == []
    root = compute_merkle_root(leaves)
    assert root == leaf
    assert verify_merkle_proof(leaf, proof, root) is True


def test_four_leaf_proof_length_two():
    leaves = [_h("a"), _h("b"), _h("c"), _h("d")]
    root = compute_merkle_root(leaves)
    for i in range(4):
        proof = compute_merkle_proof(leaves, i)
        assert len(proof) == 2
        assert verify_merkle_proof(leaves[i], proof, root) is True


def test_tampered_proof_fails():
    leaves = [_h("a"), _h("b"), _h("c"), _h("d")]
    root = compute_merkle_root(leaves)
    proof = compute_merkle_proof(leaves, 0)
    # Flip a hash in the first proof entry
    tampered = list(proof)
    tampered[0] = {"hash": _h("tampered"), "position": proof[0]["position"]}
    assert verify_merkle_proof(leaves[0], tampered, root) is False
