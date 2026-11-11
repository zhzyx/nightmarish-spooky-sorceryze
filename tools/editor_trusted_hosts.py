"""Owner-controlled macOS external editor host trust, independent of model provider.

inspect displays a signature; register requires the operator to repeat its exact
identity. Registration pins one code version. Updates require explicit registration.
No project configuration, environment variable, or command argument chooses policy.
"""

import argparse
import contextlib
import json
import os
import re
import stat
import subprocess
import sys
import uuid
from pathlib import Path


class TrustError(Exception):
    pass


def validate_entry(entry):
    if (
        len(entry) != 4
        or entry[0] not in ("host", "helper")
        or not re.fullmatch(r"[A-Za-z0-9._-]{10}", entry[1])
        or not re.fullmatch(r"[A-Za-z0-9._-]{1,512}", entry[2])
        or not re.fullmatch(r"[a-f0-9]{40}", entry[3])
    ):
        raise TrustError("invalid_exact_host_identity")
    return tuple(entry)


def decode_registry(data):
    if len(data) > 32768 or b"\x00" in data:
        raise TrustError("host_registry_invalid")
    try:
        return [validate_entry(line.split("\t")) for line in data.decode("utf-8").split("\n") if line]
    except (UnicodeError, TrustError) as error:
        raise TrustError("host_registry_invalid") from error


def encode_registry(entries):
    data = "".join("\t".join(validate_entry(entry)) + "\n" for entry in sorted(set(entries))).encode()
    if len(data) > 32768:
        raise TrustError("host_registry_too_large")
    return data


def change_registry(entries, entry, remove=False):
    entry = validate_entry(entry)
    # Registration replaces the role for this exact signed code identity.
    # Revocation remains exact: revoking a helper cannot remove a host.
    result = [value for value in entries if (value != entry if remove else value[1:] != entry[1:])]
    if not remove:
        result.append(entry)
    return result


def requirement(entry):
    _, team, identifier, digest = validate_entry(entry)
    return (
        f'anchor apple generic and identifier "{identifier}" and '
        f'certificate leaf[subject.OU] = "{team}" and cdhash H"{digest}"'
    )


def signed_identity(path, role):
    if sys.platform != "darwin":
        raise TrustError("host_registration_requires_macos")
    path = str(Path(path).resolve(strict=True))

    def codesign(*args):
        completed = subprocess.run(["/usr/bin/codesign", *args, path], capture_output=True, text=True, timeout=30)
        if completed.returncode:
            raise TrustError("host_signature_verification_failed")
        return completed.stdout + completed.stderr

    codesign("--verify", "--strict")
    details = codesign("--display", "--verbose=4")

    def field(name):
        matches = re.findall(r"^" + name + r"=(.+)$", details, re.MULTILINE)
        if len(matches) != 1:
            raise TrustError("host_signature_identity_unavailable")
        return matches[0].strip()

    entry = validate_entry((role, field("TeamIdentifier"), field("Identifier"), field("CDHash").lower()))
    codesign("--verify", "--strict", "-R", requirement(entry))
    return entry


def check_private(info, directory=False):
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if (
        not kind(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
        or (not directory and info.st_nlink != 1)
    ):
        raise TrustError("host_registry_permissions_invalid")


@contextlib.contextmanager
def registry():
    # Python's pwd database and native getpwuid resolve the same fixed home.
    if sys.platform != "darwin" or os.getuid() == 0 or os.getuid() != os.geteuid():
        raise TrustError("host_registration_requires_macos_owner")
    import fcntl
    import pwd

    home = os.open(pwd.getpwuid(os.getuid()).pw_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    directory = lock = None
    try:
        info = os.fstat(home)
        if info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise TrustError("host_home_permissions_invalid")
        try:
            os.mkdir(".gonggong-external-hosts", 0o700, dir_fd=home)
        except FileExistsError:
            pass
        directory = os.open(".gonggong-external-hosts", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=home)
        check_private(os.fstat(directory), directory=True)
        lock = os.open(".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=directory)
        check_private(os.fstat(lock))
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield directory
    finally:
        for fd in (lock, directory, home):
            if fd is not None:
                os.close(fd)


def read_registry(directory):
    try:
        fd = os.open("hosts-v1.tsv", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    except FileNotFoundError:
        return []
    with os.fdopen(fd, "rb") as stream:
        check_private(os.fstat(stream.fileno()))
        return decode_registry(stream.read(32769))


def write_registry(directory, entries):
    data = encode_registry(entries)
    name = ".pending-" + uuid.uuid4().hex
    fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.rename(name, "hosts-v1.tsv", src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:
        try:
            os.unlink(name, dir_fd=directory)
        except FileNotFoundError:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("path")
    inspect.add_argument("--role", choices=("host", "helper"), required=True)
    commands.add_parser("list")
    for action in ("register", "revoke"):
        command = commands.add_parser(action)
        command.add_argument("--role", choices=("host", "helper"), required=True)
        command.add_argument("--team", required=True)
        command.add_argument("--identifier", required=True)
        command.add_argument("--cdhash", required=True)
        if action == "register":
            command.add_argument("path")
    args = parser.parse_args(argv)
    try:
        if args.action == "inspect":
            print(json.dumps(signed_identity(args.path, args.role)))
            return 0
        entry = None
        if args.action != "list":
            entry = validate_entry((args.role, args.team, args.identifier, args.cdhash))
            if args.action == "register" and signed_identity(args.path, args.role) != entry:
                raise TrustError("observed_host_differs_from_explicit_identity")
        with registry() as directory:
            entries = read_registry(directory)
            if entry:
                entries = change_registry(entries, entry, remove=args.action == "revoke")
                write_registry(directory, entries)
            print(json.dumps({"entries": entries, "action": args.action}))
        return 0
    except (TrustError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
