from encryption import generate_hiu_key_material

# Sandbox only:
# Keeps the current HIU key material in memory.
_hiu_key_material = None


def create_hiu_exchange():
    global _hiu_key_material

    _hiu_key_material = generate_hiu_key_material()

    print("HIU ECDH key material generated")
    print("HIU nonce:", _hiu_key_material.nonce)

    return _hiu_key_material


def get_hiu_exchange():
    if _hiu_key_material is None:
        raise RuntimeError(
            "HIU ECDH key material has not been generated"
        )

    return _hiu_key_material