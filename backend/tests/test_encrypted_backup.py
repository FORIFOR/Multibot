"""Real age key generation/encryption and an actual recorded local-model artifact."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agentteam.api.service import AppService
from agentteam.operations.backup import backup, file_digest, restore
from agentteam.operations.encrypted_backup import seal, unseal
from .test_server_security import PROFILE, provision, seed_actual_work


async def test_actual_age_roundtrip_wrong_identity_corruption_and_bounds(tmp_path):
    age = os.environ.get('AGENTTEAM_AGE_BIN') or shutil.which('age')
    if not age:
        pytest.skip('install age to run the real encryption drill; CI installs a pinned release')
    keygen = str(Path(age).with_name('age-keygen'))
    private = tmp_path / 'recovery-identity.txt'
    other = tmp_path / 'unrelated-identity.txt'
    recipients = tmp_path / 'recipients.txt'
    for key in (private, other):
        subprocess.run([keygen, '-o', str(key)], check=True, capture_output=True)
    recipients.write_bytes(subprocess.run([keygen, '-y', str(private)], check=True, capture_output=True).stdout)
    access, _ = provision(tmp_path)
    svc = await AppService(tmp_path / 'data', config_yaml=PROFILE.read_text(), access_file=access).start()
    run, artifact = await seed_actual_work(svc)
    original = svc.artifacts.read_bytes(artifact)
    await svc.stop()
    snapshot = tmp_path / 'snapshot'
    backup(svc.data_dir, snapshot)
    encrypted = tmp_path / 'snapshot.tar.age'
    result = seal(snapshot, encrypted, recipients, age_bin=age)
    assert encrypted.stat().st_mode & 0o077 == 0
    assert original not in encrypted.read_bytes()
    assert private.read_bytes() not in encrypted.read_bytes()
    decoded = tmp_path / 'decoded'
    unseal(encrypted, decoded, private, expected_sha256=result['sha256'], age_bin=age)
    restore(decoded, tmp_path / 'restored')
    restored = await AppService(tmp_path / 'restored', access_file=access).start()
    try:
        stored = await restored.artifacts.get(run.run_id, artifact.artifact_id)
        assert restored.artifacts.read_bytes(stored) == original
    finally:
        await restored.stop()
    with pytest.raises(FileExistsError):
        unseal(encrypted, decoded, private, expected_sha256=result['sha256'], age_bin=age)
    with pytest.raises(ValueError, match='decryption'):
        unseal(encrypted, tmp_path / 'wrong-key', other, expected_sha256=result['sha256'], age_bin=age)
    with pytest.raises(ValueError, match='extraction limits'):
        unseal(encrypted, tmp_path / 'oversized', private, expected_sha256=result['sha256'], age_bin=age, max_bytes=1)
    damaged = tmp_path / 'damaged.tar.age'
    content = bytearray(encrypted.read_bytes()); content[-1] ^= 1; damaged.write_bytes(content)
    with pytest.raises(ValueError, match='trusted inventory'):
        unseal(damaged, tmp_path / 'bad-digest', private, expected_sha256=result['sha256'], age_bin=age)
    # Even if an operator incorrectly trusts a damaged inventory entry, age must
    # authenticate the complete stream before a plaintext snapshot is published.
    with pytest.raises(ValueError, match='decryption'):
        unseal(damaged, tmp_path / 'bad-ciphertext', private, expected_sha256=file_digest(damaged), age_bin=age)
    private.chmod(0o644)
    with pytest.raises(ValueError, match='0600'):
        unseal(encrypted, tmp_path / 'public-identity', private, expected_sha256=result['sha256'], age_bin=age)
    assert all(not (tmp_path / name).exists() for name in ['wrong-key', 'oversized', 'bad-digest', 'bad-ciphertext', 'public-identity'])
    assert not list(tmp_path.glob('.agentteam-*'))
