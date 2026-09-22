import json
import os

KEY_STORE = "hiu_keys.json"


def save_hiu_key_material(transaction_id, key_material):

    data = {}

    if os.path.exists(KEY_STORE):

        with open(KEY_STORE, "r") as f:
            data = json.load(f)

    data[transaction_id] = {
        "private_key": key_material.private_key,
        "public_key": key_material.public_key,
        "x509_public_key": key_material.x509_public_key,
        "nonce": key_material.nonce,
    }

    with open(KEY_STORE, "w") as f:
        json.dump(data, f, indent=2)


def load_hiu_key_material(transaction_id):

    if not os.path.exists(KEY_STORE):
        return None

    with open(KEY_STORE, "r") as f:
        data = json.load(f)

    item = data.get(transaction_id)

    if not item:
        return None

    class KeyMaterial:
        pass

    key = KeyMaterial()

    key.private_key = item["private_key"]
    key.public_key = item["public_key"]
    key.x509_public_key = item["x509_public_key"]
    key.nonce = item["nonce"]

    return key