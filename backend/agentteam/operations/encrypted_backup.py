"""Stream verified snapshots through the age CLI; never implement cryptography here."""
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from .backup import _regular_files, file_digest, verify


def _key_file(path: Path, *, private=False):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or (private and info.st_mode & 0o077):
        raise ValueError('age key file must be regular; private identities require mode 0600')
    if info.st_size > 65536:
        raise ValueError('age key file is too large')
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.startswith('#')]
    pattern = r'AGE-SECRET-KEY-1[0-9A-Z]+' if private else r'age1[0-9a-z]+'
    if not lines or len(lines) > 100 or any(not re.fullmatch(pattern, line) for line in lines):
        raise ValueError('only native age X25519 keys are supported; plugins and passphrases are not used')


def _destination(path: Path, source: Path):
    # Resolve only the parent so an existing dangling symlink is not followed.
    path = path.parent.resolve() / path.name
    if path.exists() or path.is_symlink():
        raise FileExistsError('destination must not exist')
    if path.is_relative_to(source) or source.is_relative_to(path):
        raise ValueError('source and destination must be separate')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def seal(source: Path, destination: Path, recipients_file: Path, *, age_bin='age'):
    source = source.resolve()
    destination = _destination(destination, source)
    _key_file(recipients_file)
    manifest = verify(source)
    fd, temporary = tempfile.mkstemp(prefix='.agentteam-seal-', dir=destination.parent)
    temporary = Path(temporary)
    proc = None
    try:
        with os.fdopen(fd, 'wb') as output:
            proc = subprocess.Popen([str(age_bin), '--encrypt', '--recipients-file', str(recipients_file.resolve())],
                                    stdin=subprocess.PIPE, stdout=output, stderr=subprocess.DEVNULL)
            with tarfile.open(fileobj=proc.stdin, mode='w|') as archive:
                for path in sorted(_regular_files(source)):
                    archive.add(path, arcname=str(path.relative_to(source)), recursive=False)
            proc.stdin.close()
            if proc.wait(timeout=60) != 0:
                raise ValueError('age encryption failed')
            output.flush(); os.fsync(output.fileno())
        if verify(source) != manifest:
            raise ValueError('snapshot changed during encryption')
        # Atomic publication without replacing an existing destination.
        os.link(temporary, destination)
        return {'destination': str(destination), 'sha256': file_digest(destination),
                'encrypted_bytes': destination.stat().st_size, 'snapshot_files': len(manifest['files']),
                'format': 'tar + age X25519', 'private_identity_required_on_backup_host': False}
    except BrokenPipeError:
        raise ValueError('age encryption failed') from None
    finally:
        if proc and proc.poll() is None:
            proc.kill(); proc.wait()
        if proc and proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        temporary.unlink(missing_ok=True)


def unseal(source: Path, destination: Path, identity_file: Path, *, expected_sha256: str,
           age_bin='age', max_bytes=10 * 1024**3):
    if source.is_symlink() or not source.is_file():
        raise ValueError('encrypted snapshot must be a regular file')
    source = source.resolve()
    destination = _destination(destination, source)
    _key_file(identity_file, private=True)
    if max_bytes < 1 or not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise ValueError('a positive extraction limit and trusted SHA-256 are required')
    if file_digest(source) != expected_sha256:
        raise ValueError('encrypted snapshot does not match the trusted inventory')
    staging = Path(tempfile.mkdtemp(prefix='.agentteam-unseal-', dir=destination.parent))
    proc = None
    reserved = False
    try:
        proc = subprocess.Popen([str(age_bin), '--decrypt', '--identity', str(identity_file.resolve()), str(source)],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        total, count, seen = 0, 0, set()
        with tarfile.open(fileobj=proc.stdout, mode='r|') as archive:
            for member in archive:
                name = PurePosixPath(member.name)
                if not member.isfile() or name.is_absolute() or '..' in name.parts or not name.parts or str(name) in seen:
                    raise ValueError('archive contains an unsafe or duplicate entry')
                total += member.size; count += 1
                if member.size < 0 or total > max_bytes or count > 100_000:
                    raise ValueError('archive exceeds extraction limits')
                if shutil.disk_usage(staging).free < member.size + 10_000_000:
                    raise ValueError('insufficient space to decrypt snapshot')
                target = staging.joinpath(*name.parts)
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with archive.extractfile(member) as input_file, target.open('xb') as output:
                    os.chmod(target, 0o600)
                    shutil.copyfileobj(input_file, output, length=1024 * 1024)
                    output.flush(); os.fsync(output.fileno())
                seen.add(str(name))
        # tar ends before the encryption stream. Drain it so age authenticates
        # every chunk, including the end marker, before publishing plaintext.
        trailing = 0
        for chunk in iter(lambda: proc.stdout.read(65536), b''):
            trailing += len(chunk)
            if trailing > 1024 * 1024 or any(chunk):
                raise ValueError('unexpected data after tar archive')
        if proc.wait(timeout=60) != 0:
            raise ValueError('age decryption or authentication failed')
        if file_digest(source) != expected_sha256:
            raise ValueError('encrypted snapshot changed during decryption')
        manifest = verify(staging)
        # Reserve a new name only after verification. Rename replaces only our
        # own empty directory; existing destinations never enter this branch.
        destination.mkdir(mode=0o700)
        reserved = True
        os.replace(staging, destination)
        reserved = False
        return {'destination': str(destination), 'verified': True, 'snapshot_files': len(manifest['files']),
                'plaintext_bytes': total, 'restore_still_required': True}
    except (tarfile.TarError, BrokenPipeError):
        raise ValueError('age decryption or snapshot archive validation failed') from None
    finally:
        if proc and proc.poll() is None:
            proc.kill(); proc.wait()
        if proc and proc.stdout:
            proc.stdout.close()
        if staging.exists():
            shutil.rmtree(staging)
        if reserved:
            destination.rmdir()
