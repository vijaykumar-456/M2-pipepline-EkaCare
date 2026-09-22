"""
Wraps the real eka-care/abdm-ecdh library (pip install abdm-ecdh) for
Phase 2's on-fetch response: when an HIU requests data, you encrypt the
serialized FHIR bundle with this before pushing it.

Per https://developer.eka.care/api-reference/user-app/abdm-connect/care-contexts/ecdh-encryption:
  - Curve25519 (Weierstrass form) key agreement
  - HKDF-SHA256 key derivation
  - AES-256-GCM encryption
This matches ABDM's HIE-CM spec -- don't hand-roll this, use the library.
"""
from abdm_ecdh import generate_key_material, encrypt, decrypt

def generate_hip_key_material():
    return generate_key_material()


def generate_hiu_key_material():
    return generate_key_material()

# def generate_hip_key_material():
#     """Call this once per encryption exchange (not reused across requests).
#     Returns an object with .private_key, .public_key, .x509_public_key,
#     .nonce -- share x509_public_key and nonce with the HIU, keep
#     private_key secret."""
#     return generate_key_material()


def calculate_checksum(plaintext: str) -> str:
    """SHA-256 hex digest of the PLAINTEXT (pre-encryption) content.
    Per Eka's data-on-fetch spec: 'Checksum of the non encrypted plain
    text fhir data' -- this MUST be computed before encrypting, not after.
    Computing it on the ciphertext instead (a real bug seen in an earlier
    draft of this pipeline) would let the HIU's integrity check silently
    fail to catch any corruption, since the checksum wouldn't correspond
    to anything they can independently verify."""
    import hashlib
    return hashlib.sha256(plaintext.encode()).hexdigest()


def encrypt_fhir_bundle(bundle_json_str: str, hip_key_material,
                         hiu_nonce: str, hiu_x509_public_key: str) -> str:
    """hiu_nonce and hiu_x509_public_key come from the HIU's on-fetch
    request -- ABDM's data-flow spec requires both parties' key material
    to derive the shared secret."""
    enc = encrypt(
        string_to_encrypt=bundle_json_str,
        sender_nonce=hip_key_material.nonce,
        requester_nonce=hiu_nonce,
        sender_private_key=hip_key_material.private_key,
        requester_public_key=hiu_x509_public_key,
    )
    return enc.encrypted_data


def decrypt_incoming_payload(encrypted_data: str, own_key_material,
                              sender_nonce: str, sender_x509_public_key: str) -> str:
    """For the HIU-parsing direction -- decrypting a bundle someone else
    sent you. Included for completeness; your primary role here is HIP
    (encrypting outbound), not HIU (decrypting inbound)."""
    dec = decrypt(
        encrypted_data=encrypted_data,
        sender_nonce=sender_nonce,
        requester_nonce=own_key_material.nonce,
        requester_private_key=own_key_material.private_key,
        sender_public_key=sender_x509_public_key,
    )
    return dec.decrypted_data


if __name__ == "__main__":
    # Round-trip self-test -- proves the library works in this environment.
    hip = generate_hip_key_material()
    hiu = generate_hiu_key_material()  # simulating the HIU's side for the test

    sample_bundle = '{"resourceType": "Bundle", "type": "document"}'
    ciphertext = encrypt_fhir_bundle(sample_bundle, hip, hiu.nonce, hiu.x509_public_key)
    print("Encrypted:", ciphertext[:60], "...")

    recovered = decrypt(
        encrypted_data=ciphertext,
        sender_nonce=hip.nonce,
        requester_nonce=hiu.nonce,
        requester_private_key=hiu.private_key,
        sender_public_key=hip.x509_public_key,
    ).decrypted_data
    print("Decrypted:", recovered)
    assert recovered == sample_bundle, "Round-trip failed!"
    print("Round-trip OK")
